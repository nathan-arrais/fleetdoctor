import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..agents.langgraph_diagnosis_graph import DiagnosisGraphState, build_diagnosis_graph
from ..models import Event, Trip
from .diagnostics import diagnose_event, diagnose_trip
from .diagnosis_tools import DiagnosisTools
from .llm_provider import LLMGenerationError, LLMSettings, OllamaProvider
from .output_validation import parse_and_validate_diagnosis


PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
DIAGNOSIS_MAX_LLM_ATTEMPTS = 3
DIAGNOSIS_JSON_RETRY_HINT = (
    "\n\nIMPORTANTE: responda SOMENTE com JSON válido no formato "
    '{"severity":"low|medium|high|critical","summary":"...","probable_causes":["..."],'
    '"recommended_actions":["..."],"evidence":["..."]}. '
    "Não inclua markdown nem texto fora do JSON."
)


@lru_cache(maxsize=16)
def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt não encontrado: {path}")
    return path.read_text(encoding="utf-8")


def _build_user_prompt(mode: str, context: dict[str, Any], tool_results: dict[str, Any]) -> str:
    if mode == "event":
        template = _load_prompt("diagnosis_event_template.txt")
        return template.format(
            event_context_json=json.dumps(context, ensure_ascii=False, indent=2),
            similar_events_json=json.dumps(tool_results.get("similar_events", []), ensure_ascii=False, indent=2),
            vehicle_history_json=json.dumps(tool_results.get("vehicle_history", {}), ensure_ascii=False, indent=2),
        )

    template = _load_prompt("diagnosis_trip_template.txt")
    return template.format(
        trip_context_json=json.dumps(context, ensure_ascii=False, indent=2),
        similar_events_json=json.dumps(tool_results.get("similar_events", []), ensure_ascii=False, indent=2),
        vehicle_history_json=json.dumps(tool_results.get("vehicle_history", {}), ensure_ascii=False, indent=2),
    )


def _should_retry_diagnosis_output(errors: list[str]) -> bool:
    lowered = " | ".join(errors).lower()
    retry_markers = [
        "resposta vazia",
        "json",
        "campo summary ausente ou vazio",
    ]
    return any(marker in lowered for marker in retry_markers)


def _pick_next_model(settings: LLMSettings, attempted_models: list[str], preferred_model: str | None = None) -> str | None:
    candidates = []
    if preferred_model:
        candidates.append(preferred_model)
    candidates.extend([settings.primary_model, settings.fallback_model])
    for model in candidates:
        if model and model not in attempted_models:
            return model
    return None


def _metadata_payload(
    diagnosis: dict[str, Any],
    *,
    source: str,
    model: str | None = None,
    latency_ms: int | None = None,
    used_tools: list[str] | None = None,
    fallback_reason: str | None = None,
    validation_warnings: list[str] | None = None,
) -> dict[str, Any]:
    output = dict(diagnosis)
    output["source"] = source
    output["model"] = model
    output["latency_ms"] = latency_ms
    output["used_tools"] = used_tools or []
    output["fallback_reason"] = fallback_reason
    output["validation_warnings"] = validation_warnings or []
    return output


def diagnose_event_with_engine(db: Session, event: Event, *, debug: bool = False, force_deterministic: bool = False) -> dict[str, Any]:
    tools = DiagnosisTools(db)
    settings = LLMSettings()
    provider = OllamaProvider(settings)

    if force_deterministic or settings.force_deterministic or settings.provider != "ollama":
        diagnosis = diagnose_event(event)
        return _metadata_payload(
            diagnosis,
            source="deterministic_fallback",
            used_tools=[],
            fallback_reason="Execução forçada no motor determinístico",
        )

    def prepare_context(state: DiagnosisGraphState) -> DiagnosisGraphState:
        try:
            return {
                **state,
                "context": tools.get_event_context(event.id),
                "used_tools": ["get_event_context", "get_similar_events", "get_vehicle_recent_history"],
            }
        except Exception as exc:
            return {**state, "validation_errors": [str(exc)], "fallback_reason": str(exc)}

    def execute_tools(state: DiagnosisGraphState) -> DiagnosisGraphState:
        if state.get("validation_errors"):
            return state
        context = state["context"]
        try:
            event_info = context["event"]
            tool_results = {
                "similar_events": tools.get_similar_events(event_info["type"], event_info["region"], limit=5),
                "vehicle_history": tools.get_vehicle_recent_history(event_info["vehicle_id"], days=30),
            }
            user_prompt = _build_user_prompt("event", context=context, tool_results=tool_results)
            return {
                **state,
                "tool_results": tool_results,
                "user_prompt": user_prompt,
                "system_prompt": _load_prompt("system_prompt.txt"),
                "llm_attempts_used": 0,
                "llm_attempted_models": [],
            }
        except Exception as exc:
            return {**state, "validation_errors": [str(exc)], "fallback_reason": str(exc)}

    def run_llm(state: DiagnosisGraphState) -> DiagnosisGraphState:
        existing_errors = list(state.get("validation_errors", []))
        attempts_used = int(state.get("llm_attempts_used", 0))
        attempted_models = list(state.get("llm_attempted_models", []))
        attempt_error_messages: list[str] = []

        while attempts_used < DIAGNOSIS_MAX_LLM_ATTEMPTS:
            next_model = _pick_next_model(settings, attempted_models)
            if not next_model:
                break

            try:
                result = provider.generate(
                    state["system_prompt"],
                    state["user_prompt"],
                    preferred_model=next_model,
                    max_model_attempts=1,
                    excluded_models=set(attempted_models),
                )
                attempts_used += max(1, len(result.get("attempts", [])))
                used_model = str(result.get("model") or next_model)
                if used_model and used_model not in attempted_models:
                    attempted_models.append(used_model)
                return {
                    **state,
                    "llm_text": result["text"],
                    "llm_model": result.get("model"),
                    "llm_latency_ms": result.get("latency_ms"),
                    "llm_attempts_used": attempts_used,
                    "llm_attempted_models": attempted_models,
                    "validation_errors": existing_errors,
                }
            except LLMGenerationError as exc:
                attempts = exc.attempts
                attempts_used += max(1, len(attempts))
                for attempt in attempts:
                    model_name = str(attempt.get("model") or "")
                    if model_name and model_name not in attempted_models:
                        attempted_models.append(model_name)
                attempt_error_messages.append(str(exc))
            except Exception as exc:
                attempts_used += 1
                attempt_error_messages.append(str(exc))

        if not attempt_error_messages:
            attempt_error_messages = ["Orçamento de tentativas da LLM esgotado"]
        last_error = " | ".join(attempt_error_messages)
        all_errors = existing_errors + attempt_error_messages
        return {
            **state,
            "llm_attempts_used": attempts_used,
            "llm_attempted_models": attempted_models,
            "validation_errors": all_errors,
            "fallback_reason": last_error,
        }

    def validate_output(state: DiagnosisGraphState) -> DiagnosisGraphState:
        if state.get("validation_errors"):
            return state

        fallback_severity = str(state["context"]["event"].get("severity", "low"))
        parsed, errors = parse_and_validate_diagnosis(state.get("llm_text", ""), fallback_severity=fallback_severity)
        attempts_used = int(state.get("llm_attempts_used", 0))
        attempted_models = list(state.get("llm_attempted_models", []))
        remaining_budget = DIAGNOSIS_MAX_LLM_ATTEMPTS - attempts_used
        if parsed is None and max(settings.retry_json_invalid, 0) > 0 and _should_retry_diagnosis_output(errors):
            if remaining_budget <= 0:
                errors = errors + ["Retry de JSON não executado: orçamento de tentativas da LLM esgotado"]
            else:
                retry_prompt = state.get("user_prompt", "") + DIAGNOSIS_JSON_RETRY_HINT
                preferred_retry_model = state.get("llm_model")
                if not preferred_retry_model:
                    preferred_retry_model = _pick_next_model(settings, attempted_models)
                try:
                    retry_result = provider.generate(
                        state.get("system_prompt", ""),
                        retry_prompt,
                        preferred_model=preferred_retry_model,
                        max_model_attempts=1,
                        excluded_models=None if preferred_retry_model else set(attempted_models),
                    )
                    attempts_used += max(1, len(retry_result.get("attempts", [])))
                    used_model = str(retry_result.get("model") or preferred_retry_model or "")
                    if used_model and used_model not in attempted_models:
                        attempted_models.append(used_model)
                    retry_parsed, retry_errors = parse_and_validate_diagnosis(
                        retry_result.get("text", ""),
                        fallback_severity=fallback_severity,
                    )
                    if retry_parsed is not None:
                        retry_note = "Retry de JSON aplicado após falha inicial: " + "; ".join(errors)
                        return {
                            **state,
                            "llm_text": retry_result.get("text", ""),
                            "llm_model": retry_result.get("model"),
                            "llm_latency_ms": retry_result.get("latency_ms"),
                            "llm_attempts_used": attempts_used,
                            "llm_attempted_models": attempted_models,
                            "diagnosis": _metadata_payload(
                                retry_parsed,
                                source="llm",
                                model=retry_result.get("model"),
                                latency_ms=retry_result.get("latency_ms"),
                                used_tools=state.get("used_tools"),
                                validation_warnings=[retry_note] + retry_errors,
                            ),
                            "source": "llm",
                        }
                    errors = errors + ["Retry de JSON falhou: " + "; ".join(retry_errors)]
                except Exception as retry_exc:
                    errors = errors + [f"Retry de JSON falhou: {retry_exc}"]
        if parsed is None:
            return {**state, "validation_errors": errors, "fallback_reason": "; ".join(errors)}
        return {
            **state,
            "diagnosis": _metadata_payload(
                parsed,
                source="llm",
                model=state.get("llm_model"),
                latency_ms=state.get("llm_latency_ms"),
                used_tools=state.get("used_tools"),
                validation_warnings=errors,
            ),
            "source": "llm",
        }

    def run_fallback(state: DiagnosisGraphState) -> DiagnosisGraphState:
        fallback = diagnose_event(event)
        return {
            **state,
            "diagnosis": _metadata_payload(
                fallback,
                source="deterministic_fallback",
                model=state.get("llm_model"),
                latency_ms=state.get("llm_latency_ms"),
                used_tools=state.get("used_tools"),
                fallback_reason=state.get("fallback_reason") or "Fallback acionado por validação",
                validation_warnings=state.get("validation_errors", []),
            ),
            "source": "deterministic_fallback",
        }

    graph = build_diagnosis_graph(
        prepare_context=prepare_context,
        execute_tools=execute_tools,
        run_llm=run_llm,
        validate_output=validate_output,
        run_fallback=run_fallback,
    )
    result = graph.invoke({"mode": "event"})
    diagnosis = result.get("diagnosis")
    if not diagnosis:
        fallback = diagnose_event(event)
        diagnosis = _metadata_payload(
            fallback,
            source="deterministic_fallback",
            used_tools=[],
            fallback_reason="Fallback final por ausência de diagnóstico no grafo",
        )

    if not debug:
        diagnosis = dict(diagnosis)
        diagnosis.pop("fallback_reason", None)
        if diagnosis.get("source") == "llm":
            diagnosis["fallback_reason"] = None
    return diagnosis


def diagnose_trip_with_engine(db: Session, trip: Trip, *, debug: bool = False, force_deterministic: bool = False) -> dict[str, Any]:
    tools = DiagnosisTools(db)
    settings = LLMSettings()
    provider = OllamaProvider(settings)

    if force_deterministic or settings.force_deterministic or settings.provider != "ollama":
        diagnosis = diagnose_trip(db, trip)
        return _metadata_payload(
            diagnosis,
            source="deterministic_fallback",
            used_tools=[],
            fallback_reason="Execução forçada no motor determinístico",
        )

    def prepare_context(state: DiagnosisGraphState) -> DiagnosisGraphState:
        try:
            return {
                **state,
                "context": tools.get_trip_context(trip.id),
                "used_tools": ["get_trip_context", "get_similar_events", "get_vehicle_recent_history"],
            }
        except Exception as exc:
            return {**state, "validation_errors": [str(exc)], "fallback_reason": str(exc)}

    def execute_tools(state: DiagnosisGraphState) -> DiagnosisGraphState:
        if state.get("validation_errors"):
            return state
        context = state["context"]
        try:
            events = context.get("events", [])
            anchor_type = events[0]["type"] if events else "route_deviation"
            region = context["vehicle"].get("region", "")
            vehicle_id = context["vehicle"]["id"]
            tool_results = {
                "similar_events": tools.get_similar_events(anchor_type, region, limit=5),
                "vehicle_history": tools.get_vehicle_recent_history(vehicle_id, days=30),
            }
            user_prompt = _build_user_prompt("trip", context=context, tool_results=tool_results)
            return {
                **state,
                "tool_results": tool_results,
                "user_prompt": user_prompt,
                "system_prompt": _load_prompt("system_prompt.txt"),
                "llm_attempts_used": 0,
                "llm_attempted_models": [],
            }
        except Exception as exc:
            return {**state, "validation_errors": [str(exc)], "fallback_reason": str(exc)}

    def run_llm(state: DiagnosisGraphState) -> DiagnosisGraphState:
        existing_errors = list(state.get("validation_errors", []))
        attempts_used = int(state.get("llm_attempts_used", 0))
        attempted_models = list(state.get("llm_attempted_models", []))
        attempt_error_messages: list[str] = []

        while attempts_used < DIAGNOSIS_MAX_LLM_ATTEMPTS:
            next_model = _pick_next_model(settings, attempted_models)
            if not next_model:
                break

            try:
                result = provider.generate(
                    state["system_prompt"],
                    state["user_prompt"],
                    preferred_model=next_model,
                    max_model_attempts=1,
                    excluded_models=set(attempted_models),
                )
                attempts_used += max(1, len(result.get("attempts", [])))
                used_model = str(result.get("model") or next_model)
                if used_model and used_model not in attempted_models:
                    attempted_models.append(used_model)
                return {
                    **state,
                    "llm_text": result["text"],
                    "llm_model": result.get("model"),
                    "llm_latency_ms": result.get("latency_ms"),
                    "llm_attempts_used": attempts_used,
                    "llm_attempted_models": attempted_models,
                    "validation_errors": existing_errors,
                }
            except LLMGenerationError as exc:
                attempts = exc.attempts
                attempts_used += max(1, len(attempts))
                for attempt in attempts:
                    model_name = str(attempt.get("model") or "")
                    if model_name and model_name not in attempted_models:
                        attempted_models.append(model_name)
                attempt_error_messages.append(str(exc))
            except Exception as exc:
                attempts_used += 1
                attempt_error_messages.append(str(exc))

        if not attempt_error_messages:
            attempt_error_messages = ["Orçamento de tentativas da LLM esgotado"]
        last_error = " | ".join(attempt_error_messages)
        all_errors = existing_errors + attempt_error_messages
        return {
            **state,
            "llm_attempts_used": attempts_used,
            "llm_attempted_models": attempted_models,
            "validation_errors": all_errors,
            "fallback_reason": last_error,
        }

    def validate_output(state: DiagnosisGraphState) -> DiagnosisGraphState:
        if state.get("validation_errors"):
            return state
        fallback_severity = "low"
        parsed, errors = parse_and_validate_diagnosis(state.get("llm_text", ""), fallback_severity=fallback_severity)
        attempts_used = int(state.get("llm_attempts_used", 0))
        attempted_models = list(state.get("llm_attempted_models", []))
        remaining_budget = DIAGNOSIS_MAX_LLM_ATTEMPTS - attempts_used
        if parsed is None and max(settings.retry_json_invalid, 0) > 0 and _should_retry_diagnosis_output(errors):
            if remaining_budget <= 0:
                errors = errors + ["Retry de JSON não executado: orçamento de tentativas da LLM esgotado"]
            else:
                retry_prompt = state.get("user_prompt", "") + DIAGNOSIS_JSON_RETRY_HINT
                preferred_retry_model = state.get("llm_model")
                if not preferred_retry_model:
                    preferred_retry_model = _pick_next_model(settings, attempted_models)
                try:
                    retry_result = provider.generate(
                        state.get("system_prompt", ""),
                        retry_prompt,
                        preferred_model=preferred_retry_model,
                        max_model_attempts=1,
                        excluded_models=None if preferred_retry_model else set(attempted_models),
                    )
                    attempts_used += max(1, len(retry_result.get("attempts", [])))
                    used_model = str(retry_result.get("model") or preferred_retry_model or "")
                    if used_model and used_model not in attempted_models:
                        attempted_models.append(used_model)
                    retry_parsed, retry_errors = parse_and_validate_diagnosis(
                        retry_result.get("text", ""),
                        fallback_severity=fallback_severity,
                    )
                    if retry_parsed is not None:
                        retry_note = "Retry de JSON aplicado após falha inicial: " + "; ".join(errors)
                        return {
                            **state,
                            "llm_text": retry_result.get("text", ""),
                            "llm_model": retry_result.get("model"),
                            "llm_latency_ms": retry_result.get("latency_ms"),
                            "llm_attempts_used": attempts_used,
                            "llm_attempted_models": attempted_models,
                            "diagnosis": _metadata_payload(
                                retry_parsed,
                                source="llm",
                                model=retry_result.get("model"),
                                latency_ms=retry_result.get("latency_ms"),
                                used_tools=state.get("used_tools"),
                                validation_warnings=[retry_note] + retry_errors,
                            ),
                            "source": "llm",
                        }
                    errors = errors + ["Retry de JSON falhou: " + "; ".join(retry_errors)]
                except Exception as retry_exc:
                    errors = errors + [f"Retry de JSON falhou: {retry_exc}"]
        if parsed is None:
            return {**state, "validation_errors": errors, "fallback_reason": "; ".join(errors)}
        return {
            **state,
            "diagnosis": _metadata_payload(
                parsed,
                source="llm",
                model=state.get("llm_model"),
                latency_ms=state.get("llm_latency_ms"),
                used_tools=state.get("used_tools"),
                validation_warnings=errors,
            ),
            "source": "llm",
        }

    def run_fallback(state: DiagnosisGraphState) -> DiagnosisGraphState:
        fallback = diagnose_trip(db, trip)
        return {
            **state,
            "diagnosis": _metadata_payload(
                fallback,
                source="deterministic_fallback",
                model=state.get("llm_model"),
                latency_ms=state.get("llm_latency_ms"),
                used_tools=state.get("used_tools"),
                fallback_reason=state.get("fallback_reason") or "Fallback acionado por validação",
                validation_warnings=state.get("validation_errors", []),
            ),
            "source": "deterministic_fallback",
        }

    graph = build_diagnosis_graph(
        prepare_context=prepare_context,
        execute_tools=execute_tools,
        run_llm=run_llm,
        validate_output=validate_output,
        run_fallback=run_fallback,
    )
    result = graph.invoke({"mode": "trip"})
    diagnosis = result.get("diagnosis")
    if not diagnosis:
        fallback = diagnose_trip(db, trip)
        diagnosis = _metadata_payload(
            fallback,
            source="deterministic_fallback",
            used_tools=[],
            fallback_reason="Fallback final por ausência de diagnóstico no grafo",
        )

    if not debug:
        diagnosis = dict(diagnosis)
        diagnosis.pop("fallback_reason", None)
        if diagnosis.get("source") == "llm":
            diagnosis["fallback_reason"] = None
    return diagnosis

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..agents.langgraph_chat_graph import ChatGraphState, build_chat_graph
from ..models import ChatMessage, ChatSession
from .chat_tools import ChatTools
from .llm_provider import LLMGenerationError, LLMSettings, OllamaProvider, build_chat_llm_settings
from .output_validation import parse_and_validate_chat_response


PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
CHAT_MAX_LLM_ATTEMPTS = 2
CHAT_JSON_RETRY_HINT = (
    "\n\nIMPORTANTE: responda SOMENTE com JSON valido no formato "
    '{"answer":"...","citations":["..."],"follow_up_questions":["..."]}. '
    "Nao inclua markdown nem texto fora do JSON."
)


def _now_utc() -> datetime:
    return datetime.utcnow()


@lru_cache(maxsize=16)
def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt nao encontrado: {path}")
    return path.read_text(encoding="utf-8")


def _safe_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _safe_json_load_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return []
    except json.JSONDecodeError:
        return []


def _message_to_out(message: ChatMessage) -> dict[str, Any]:
    return {
        "id": message.id,
        "session_id": message.session_id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at,
        "source": message.source,
        "model": message.model,
        "latency_ms": message.latency_ms,
        "used_tools": _safe_json_load_list(message.used_tools_json),
        "fallback_reason": message.fallback_reason,
        "validation_warnings": _safe_json_load_list(message.validation_warnings_json),
        "citations": _safe_json_load_list(message.citations_json),
        "follow_up_questions": _safe_json_load_list(message.follow_up_questions_json),
    }


def create_chat_session(db: Session, title: str | None = None) -> ChatSession:
    created_at = _now_utc()
    normalized_title = (title or "").strip()
    if not normalized_title:
        normalized_title = f"Conversa {created_at.strftime('%d/%m %H:%M')}"
    session = ChatSession(
        title=normalized_title,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_chat_sessions(db: Session, limit: int = 50) -> list[ChatSession]:
    safe_limit = max(1, min(limit, 200))
    return db.query(ChatSession).order_by(ChatSession.updated_at.desc()).limit(safe_limit).all()


def get_chat_session_messages(db: Session, session_id: int, limit: int = 100) -> list[dict[str, Any]]:
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise ValueError("Sessao de chat nao encontrada")
    safe_limit = max(1, min(limit, 500))
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(safe_limit)
        .all()
    )
    ordered = list(reversed(rows))
    return [_message_to_out(message) for message in ordered]


def _infer_intent(question: str) -> str:
    text = question.lower()
    if any(token in text for token in ["dashboard", "kpi", "indicador", "visao geral", "resumo"]):
        return "dashboard"
    if any(token in text for token in ["triagem", "evento", "ocorrencia", "ocorrência", "alerta"]):
        return "triage"
    if any(token in text for token in ["veiculo", "veículo", "placa", "odometro", "odômetro"]):
        return "vehicle"
    if any(token in text for token in ["viagem", "trip", "rota", "motorista"]):
        return "trip"
    if any(token in text for token in ["risco", "critico", "crítico", "severidade"]):
        return "risks"
    return "general"


def _extract_ids(question: str) -> dict[str, int]:
    extracted: dict[str, int] = {}
    vehicle_match = re.search(r"(veiculo|veículo|vehicle)\s*#?\s*(\d+)", question, flags=re.IGNORECASE)
    trip_match = re.search(r"(viagem|trip)\s*#?\s*(\d+)", question, flags=re.IGNORECASE)
    if vehicle_match:
        extracted["vehicle_id"] = int(vehicle_match.group(2))
    if trip_match:
        extracted["trip_id"] = int(trip_match.group(2))
    return extracted


def _collect_tool_results(tools: ChatTools, intent: str, ids: dict[str, int], question: str) -> tuple[dict[str, Any], list[str], list[str]]:
    tool_results: dict[str, Any] = {}
    used_tools: list[str] = []
    tool_warnings: list[str] = []

    def call(tool_name: str, fn, *args, **kwargs):
        try:
            tool_results[tool_name] = fn(*args, **kwargs)
            used_tools.append(tool_name)
        except Exception as exc:
            tool_warnings.append(f"{tool_name}: {exc}")

    if intent in {"dashboard", "general", "risks"}:
        call("get_dashboard_snapshot", tools.get_dashboard_snapshot)
    if intent in {"triage", "general"}:
        call("search_events", tools.search_events, q=question, limit=10)
    if intent == "vehicle":
        vehicle_id = ids.get("vehicle_id")
        if vehicle_id is None:
            tool_warnings.append("Nao foi possivel extrair vehicle_id da pergunta")
        else:
            call("get_vehicle_overview", tools.get_vehicle_overview, vehicle_id)
    if intent == "trip":
        trip_id = ids.get("trip_id")
        if trip_id is None:
            tool_warnings.append("Nao foi possivel extrair trip_id da pergunta")
        else:
            call("get_trip_overview", tools.get_trip_overview, trip_id)

    call("get_top_risks", tools.get_top_risks, 7)
    return tool_results, used_tools, tool_warnings


def _build_user_prompt(
    question: str,
    intent: str,
    history: list[dict[str, str]],
    tool_results: dict[str, Any],
) -> str:
    template = _load_prompt("chat_response_template.txt")
    return template.format(
        intent=intent,
        question=question,
        history_json=json.dumps(history, ensure_ascii=False, indent=2),
        tool_results_json=json.dumps(tool_results, ensure_ascii=False, indent=2),
    )


def _should_retry_chat_output(errors: list[str]) -> bool:
    lowered = " | ".join(errors).lower()
    retry_markers = [
        "resposta vazia",
        "json",
        "campo answer ausente ou vazio",
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


def _build_fallback_answer(intent: str, question: str, tool_results: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    lines = []
    citations = []

    if "get_dashboard_snapshot" in tool_results:
        citations.append("get_dashboard_snapshot")
        kpis = tool_results["get_dashboard_snapshot"].get("kpis", {})
        lines.append(
            "Resumo atual: "
            f"{kpis.get('events_total', 0)} eventos, "
            f"{kpis.get('events_critical', 0)} criticos, "
            f"{kpis.get('active_vehicles', 0)} veiculos ativos."
        )
    if "get_top_risks" in tool_results:
        citations.append("get_top_risks")
        top_types = tool_results["get_top_risks"].get("events_by_type", [])[:3]
        if top_types:
            summary = ", ".join(f"{item.get('type')}: {item.get('count')}" for item in top_types)
            lines.append(f"Principais tipos de risco recentes: {summary}.")
    if "get_vehicle_overview" in tool_results:
        citations.append("get_vehicle_overview")
        vehicle = tool_results["get_vehicle_overview"].get("vehicle", {})
        lines.append(
            f"Veiculo analisado: {vehicle.get('code')} ({vehicle.get('plate')}), "
            f"status {vehicle.get('status')}."
        )
    if "get_trip_overview" in tool_results:
        citations.append("get_trip_overview")
        trip = tool_results["get_trip_overview"].get("trip", {})
        lines.append(
            f"Viagem #{trip.get('id')} de {trip.get('origin')} para {trip.get('destination')} "
            f"com status {trip.get('status')}."
        )
    if "search_events" in tool_results:
        citations.append("search_events")
        event_count = len(tool_results["search_events"])
        lines.append(f"Busca de triagem retornou {event_count} eventos relevantes para a pergunta.")

    if not lines:
        lines.append("Nao consegui consolidar dados suficientes para responder com precisao nesta consulta.")

    if warnings:
        lines.append("Observacao: houve limitacoes na coleta de contexto para esta resposta.")

    has_vehicle_id = re.search(r"(veiculo|veículo|vehicle)\s*#?\s*(\d+)", question, flags=re.IGNORECASE) is not None
    has_trip_id = re.search(r"(viagem|trip)\s*#?\s*(\d+)", question, flags=re.IGNORECASE) is not None

    if intent == "vehicle" and not has_vehicle_id:
        follow_up = ["Informe o ID do veiculo no formato: veiculo 12."]
    elif intent == "trip" and not has_trip_id:
        follow_up = ["Informe o ID da viagem no formato: viagem 8."]
    else:
        follow_up = ["Quer que eu detalhe por severidade ou por regiao?"]

    return {
        "answer": " ".join(lines),
        "citations": citations,
        "follow_up_questions": follow_up,
    }


def ask_chat(
    db: Session,
    *,
    session_id: int,
    message: str,
    debug: bool = False,
    force_deterministic: bool = False,
) -> dict[str, Any]:
    normalized_message = message.strip()
    if not normalized_message:
        raise ValueError("Mensagem vazia")

    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise ValueError("Sessao de chat nao encontrada")

    now = _now_utc()
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=normalized_message,
        created_at=now,
    )
    db.add(user_message)

    if session.title.startswith("Conversa ") and len(normalized_message) > 6:
        session.title = normalized_message[:60].strip()
    session.updated_at = now
    db.commit()
    db.refresh(user_message)
    db.refresh(session)

    tools = ChatTools(db)
    base_settings = LLMSettings()
    settings = build_chat_llm_settings(base_settings)
    provider = OllamaProvider(settings)
    intent = _infer_intent(normalized_message)
    ids = _extract_ids(normalized_message)

    if force_deterministic or base_settings.force_deterministic or settings.provider != "ollama":
        tool_results, used_tools, tool_warnings = _collect_tool_results(tools, intent, ids, normalized_message)
        payload = _build_fallback_answer(intent, normalized_message, tool_results, tool_warnings)
        answer_payload = {
            **payload,
            "source": "deterministic_fallback",
            "model": None,
            "latency_ms": None,
            "used_tools": used_tools,
            "fallback_reason": "Execucao forcada no motor deterministico",
            "validation_warnings": tool_warnings,
        }
    else:
        def load_memory(state: ChatGraphState) -> ChatGraphState:
            rows = (
                db.query(ChatMessage)
                .filter(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.desc())
                .limit(12)
                .all()
            )
            history = [{"role": row.role, "content": row.content} for row in reversed(rows)]
            return {**state, "history": history}

        def route_intent_node(state: ChatGraphState) -> ChatGraphState:
            detected_intent = _infer_intent(state["question"])
            extracted_ids = _extract_ids(state["question"])
            return {**state, "intent": detected_intent, "extracted_ids": extracted_ids}

        def execute_tools_node(state: ChatGraphState) -> ChatGraphState:
            tool_results, used_tools, tool_warnings = _collect_tool_results(
                tools,
                state["intent"],
                state.get("extracted_ids", {}),
                state["question"],
            )
            user_prompt = _build_user_prompt(
                question=state["question"],
                intent=state["intent"],
                history=state.get("history", []),
                tool_results=tool_results,
            )
            return {
                **state,
                "tool_results": tool_results,
                "used_tools": used_tools,
                "user_prompt": user_prompt,
                "system_prompt": _load_prompt("chat_system_prompt.txt"),
                "validation_errors": tool_warnings,
                "llm_attempts_used": 0,
                "llm_attempted_models": [],
            }

        def run_llm_node(state: ChatGraphState) -> ChatGraphState:
            existing_errors = list(state.get("validation_errors", []))
            attempts_used = int(state.get("llm_attempts_used", 0))
            attempted_models = list(state.get("llm_attempted_models", []))
            attempt_error_messages: list[str] = []

            while attempts_used < CHAT_MAX_LLM_ATTEMPTS:
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
                    used_model = str(result.get("model") or next_model)
                    if used_model and used_model not in attempted_models:
                        attempted_models.append(used_model)
                    attempts_used += max(1, len(result.get("attempts", [])))
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
                attempt_error_messages = ["Orcamento de tentativas da LLM esgotado"]
            last_error = " | ".join(attempt_error_messages)
            all_errors = existing_errors + attempt_error_messages
            return {
                **state,
                "llm_attempts_used": attempts_used,
                "llm_attempted_models": attempted_models,
                "validation_errors": all_errors,
                "fallback_reason": last_error,
            }

        def validate_output_node(state: ChatGraphState) -> ChatGraphState:
            errors = list(state.get("validation_errors", []))
            parsed, warnings = parse_and_validate_chat_response(state.get("llm_text", ""))
            if parsed is None:
                parse_errors = list(warnings)
                should_retry = max(settings.retry_json_invalid, 0) > 0 and _should_retry_chat_output(parse_errors)
                attempts_used = int(state.get("llm_attempts_used", 0))
                attempted_models = list(state.get("llm_attempted_models", []))
                remaining_budget = CHAT_MAX_LLM_ATTEMPTS - attempts_used
                if should_retry and remaining_budget > 0:
                    retry_prompt = state.get("user_prompt", "") + CHAT_JSON_RETRY_HINT
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
                        retry_parsed, retry_warnings = parse_and_validate_chat_response(retry_result.get("text", ""))
                        if retry_parsed is not None:
                            retry_note = "Retry de JSON aplicado apos falha inicial: " + "; ".join(parse_errors)
                            return {
                                **state,
                                "llm_text": retry_result.get("text", ""),
                                "llm_model": retry_result.get("model"),
                                "llm_latency_ms": retry_result.get("latency_ms"),
                                "llm_attempts_used": attempts_used,
                                "llm_attempted_models": attempted_models,
                                "answer_payload": {
                                    "answer": retry_parsed["answer"],
                                    "citations": retry_parsed.get("citations", []),
                                    "follow_up_questions": retry_parsed.get("follow_up_questions", []),
                                    "source": "llm",
                                    "model": retry_result.get("model"),
                                    "latency_ms": retry_result.get("latency_ms"),
                                    "used_tools": state.get("used_tools", []),
                                    "fallback_reason": None,
                                    "validation_warnings": errors + [retry_note] + retry_warnings,
                                },
                                "validation_errors": [],
                            }
                        parse_errors.append("Retry de JSON falhou: " + "; ".join(retry_warnings))
                    except Exception as retry_exc:
                        parse_errors.append(f"Retry de JSON falhou: {retry_exc}")
                elif should_retry and remaining_budget <= 0:
                    parse_errors.append("Retry de JSON nao executado: orcamento de tentativas da LLM esgotado")

                all_errors = errors + parse_errors
                return {**state, "validation_errors": all_errors, "fallback_reason": "; ".join(all_errors)}
            return {
                **state,
                "answer_payload": {
                    "answer": parsed["answer"],
                    "citations": parsed.get("citations", []),
                    "follow_up_questions": parsed.get("follow_up_questions", []),
                    "source": "llm",
                    "model": state.get("llm_model"),
                    "latency_ms": state.get("llm_latency_ms"),
                    "used_tools": state.get("used_tools", []),
                    "fallback_reason": None,
                    "validation_warnings": errors + warnings,
                },
                "validation_errors": [],
            }

        def fallback_response_node(state: ChatGraphState) -> ChatGraphState:
            tool_results = state.get("tool_results", {})
            warnings = state.get("validation_errors", [])
            payload = _build_fallback_answer(state.get("intent", "general"), state["question"], tool_results, warnings)
            return {
                **state,
                "answer_payload": {
                    **payload,
                    "source": "deterministic_fallback",
                    "model": state.get("llm_model"),
                    "latency_ms": state.get("llm_latency_ms"),
                    "used_tools": state.get("used_tools", []),
                    "fallback_reason": state.get("fallback_reason") or "Falha na resposta estruturada do modelo",
                    "validation_warnings": warnings,
                },
                "validation_errors": [],
            }

        graph = build_chat_graph(
            load_memory=load_memory,
            route_intent=route_intent_node,
            execute_tools=execute_tools_node,
            run_llm=run_llm_node,
            validate_output=validate_output_node,
            fallback_response=fallback_response_node,
        )
        result = graph.invoke({"session_id": session.id, "question": normalized_message})
        answer_payload = result.get("answer_payload")
        if not answer_payload:
            answer_payload = {
                "answer": "Nao foi possivel gerar resposta para esta pergunta.",
                "citations": [],
                "follow_up_questions": ["Pode reformular a pergunta com mais contexto?"],
                "source": "deterministic_fallback",
                "model": None,
                "latency_ms": None,
                "used_tools": [],
                "fallback_reason": "Falha final do grafo de chat",
                "validation_warnings": [],
            }

    assistant_message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer_payload["answer"],
        created_at=_now_utc(),
        source=answer_payload.get("source"),
        model=answer_payload.get("model"),
        latency_ms=answer_payload.get("latency_ms"),
        used_tools_json=_safe_json_dumps(answer_payload.get("used_tools", [])),
        fallback_reason=answer_payload.get("fallback_reason"),
        validation_warnings_json=_safe_json_dumps(answer_payload.get("validation_warnings", [])),
        citations_json=_safe_json_dumps(answer_payload.get("citations", [])),
        follow_up_questions_json=_safe_json_dumps(answer_payload.get("follow_up_questions", [])),
    )
    db.add(assistant_message)
    session.updated_at = _now_utc()
    db.commit()
    db.refresh(assistant_message)

    response_payload = {
        "session_id": session.id,
        "answer": answer_payload["answer"],
        "citations": answer_payload.get("citations", []),
        "follow_up_questions": answer_payload.get("follow_up_questions", []),
        "source": answer_payload.get("source"),
        "model": answer_payload.get("model"),
        "latency_ms": answer_payload.get("latency_ms"),
        "used_tools": answer_payload.get("used_tools", []),
        "fallback_reason": answer_payload.get("fallback_reason"),
        "validation_warnings": answer_payload.get("validation_warnings", []),
        "user_message": _message_to_out(user_message),
        "assistant_message": _message_to_out(assistant_message),
    }

    if not debug:
        response_payload["user_message"]["validation_warnings"] = []
        if response_payload["source"] == "llm":
            response_payload["fallback_reason"] = None
    return response_payload

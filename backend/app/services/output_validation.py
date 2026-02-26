import json
from typing import Any


VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def _extract_json_candidate(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if not text:
        raise ValueError("Resposta vazia do modelo")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("JSON recebido não é objeto")
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Não foi possível localizar JSON válido na resposta")
        sliced = text[start : end + 1]
        parsed = json.loads(sliced)
        if not isinstance(parsed, dict):
            raise ValueError("JSON recortado não é objeto")
        return parsed


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for element in value:
        if isinstance(element, str):
            normalized = element.strip()
            if normalized:
                items.append(normalized)
    return items


def parse_and_validate_diagnosis(raw_text: str, fallback_severity: str = "low") -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        payload = _extract_json_candidate(raw_text)
    except Exception as exc:
        return None, [str(exc)]

    severity = str(payload.get("severity", fallback_severity)).strip().lower()
    if severity not in VALID_SEVERITIES:
        errors.append(f"Severidade inválida retornada pelo modelo: {severity!r}")
        severity = fallback_severity if fallback_severity in VALID_SEVERITIES else "low"

    summary = str(payload.get("summary", "")).strip()
    if not summary:
        errors.append("Campo summary ausente ou vazio")
        summary = "Diagnóstico gerado sem resumo válido."

    probable_causes = _as_str_list(payload.get("probable_causes"))
    if not probable_causes:
        errors.append("Campo probable_causes ausente ou vazio")
        probable_causes = ["Dados insuficientes para inferência robusta"]

    recommended_actions = _as_str_list(payload.get("recommended_actions"))
    if not recommended_actions:
        errors.append("Campo recommended_actions ausente ou vazio")
        recommended_actions = ["Validar manualmente o evento com o time operacional"]

    evidence = _as_str_list(payload.get("evidence"))
    if not evidence:
        errors.append("Campo evidence ausente ou vazio")
        evidence = ["Não houve evidência estruturada retornada pelo modelo"]

    normalized = {
        "severity": severity,
        "summary": summary,
        "probable_causes": probable_causes,
        "recommended_actions": recommended_actions,
        "evidence": evidence,
    }
    return normalized, errors


def parse_and_validate_chat_response(raw_text: str, allow_text_fallback: bool = True) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    try:
        payload = _extract_json_candidate(raw_text)
    except Exception as exc:
        normalized_text = raw_text.strip()
        if allow_text_fallback and normalized_text:
            warnings.append(f"Resposta em texto livre; parse tolerante aplicado: {exc}")
            warnings.append("Campo citations ausente ou vazio")
            warnings.append("Campo follow_up_questions ausente ou vazio")
            return {
                "answer": normalized_text,
                "citations": [],
                "follow_up_questions": [],
            }, warnings
        return None, [str(exc)]

    answer = str(payload.get("answer", "")).strip()
    if not answer:
        answer = str(payload.get("summary", "")).strip()
    if not answer:
        return None, ["Campo answer ausente ou vazio na resposta do modelo"]

    citations = _as_str_list(payload.get("citations"))
    if not citations:
        warnings.append("Campo citations ausente ou vazio")

    follow_up_questions = _as_str_list(payload.get("follow_up_questions"))
    if not follow_up_questions:
        warnings.append("Campo follow_up_questions ausente ou vazio")

    normalized = {
        "answer": answer,
        "citations": citations,
        "follow_up_questions": follow_up_questions,
    }
    return normalized, warnings

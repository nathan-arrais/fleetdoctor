from app.services.output_validation import parse_and_validate_chat_response, parse_and_validate_diagnosis


def test_parse_output_parcial_gera_payload_com_warnings():
    raw = '{"severity":"high","summary":"Teste","probable_causes":["A"],"recommended_actions":["B"]}'
    payload, warnings = parse_and_validate_diagnosis(raw, fallback_severity="medium")

    assert payload is not None
    assert payload["severity"] == "high"
    assert payload["summary"] == "Teste"
    assert payload["probable_causes"] == ["A"]
    assert payload["recommended_actions"] == ["B"]
    assert isinstance(payload["evidence"], list)
    assert len(warnings) >= 1


def test_parse_chat_output_valido():
    raw = '{"answer":"Resumo operacional","citations":["get_dashboard_snapshot"],"follow_up_questions":["Deseja recorte por região?"]}'
    payload, warnings = parse_and_validate_chat_response(raw)

    assert payload is not None
    assert payload["answer"] == "Resumo operacional"
    assert payload["citations"] == ["get_dashboard_snapshot"]
    assert payload["follow_up_questions"] == ["Deseja recorte por região?"]
    assert warnings == []


def test_parse_chat_output_texto_livre_aplica_parse_tolerante():
    raw = "Resumo operacional: riscos de temperatura e ociosidade acima da média."
    payload, warnings = parse_and_validate_chat_response(raw)

    assert payload is not None
    assert payload["answer"] == raw
    assert payload["citations"] == []
    assert payload["follow_up_questions"] == []
    assert any("parse tolerante" in warning.lower() for warning in warnings)


def test_parse_chat_output_vazio_sem_json_retorna_erro():
    payload, warnings = parse_and_validate_chat_response("   ")
    assert payload is None
    assert warnings

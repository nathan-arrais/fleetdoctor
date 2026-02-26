from app.services.output_validation import parse_and_validate_diagnosis


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

def test_diagnosis_por_evento_retorna_payload_esperado(client):
    triage_response = client.get("/api/triage/events", params={"page_size": 1})
    assert triage_response.status_code == 200
    triage_data = triage_response.json()
    assert triage_data["total"] > 0

    event_id = triage_data["items"][0]["id"]
    diagnosis_response = client.post("/api/diagnosis", json={"event_id": event_id})

    assert diagnosis_response.status_code == 200
    payload = diagnosis_response.json()
    assert payload["severity"] in {"low", "medium", "high", "critical"}
    assert payload["summary"]
    assert isinstance(payload["probable_causes"], list)
    assert isinstance(payload["recommended_actions"], list)
    assert isinstance(payload["evidence"], list)

CSV_IMPORT_INVALIDO = """vehicle_id,plate,trip_id,event_type,severity,timestamp,description,value_num
IMPORT-TESTE-001,ZZZ0001,,tipo_invalido,severidade_invalida,data-invalida,Evento importado de teste,11
"""


def test_upload_import_normaliza_campos_invalidos(client):
    response = client.post(
        "/api/upload/import",
        files={"file": ("import.csv", CSV_IMPORT_INVALIDO.encode("utf-8"), "text/csv")},
    )
    assert response.status_code == 200

    payload = response.json()
    assert payload["imported"] == 1
    assert "warnings" in payload

    triage_response = client.get("/api/triage/events", params={"q": "Evento importado de teste", "page_size": 50})
    assert triage_response.status_code == 200

    items = triage_response.json()["items"]
    item = next((current for current in items if current["description"] == "Evento importado de teste"), None)
    assert item is not None
    assert item["type"] == "route_deviation"
    assert item["severity"] == "low"

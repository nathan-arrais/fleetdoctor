def test_preview_de_relatorio_escapa_html_de_filtros(client):
    response = client.post(
        "/api/reports/generate",
        json={
            "type": "executive",
            "start": "2026-01-01",
            "end": "2026-12-31",
            "q": "<script>alert(1)</script>",
        },
    )
    assert response.status_code == 200

    report_id = response.json()["id"]
    preview_response = client.get(f"/api/reports/{report_id}/preview")
    assert preview_response.status_code == 200

    html = preview_response.text
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html

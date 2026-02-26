def test_llm_health_retorna_configuracao_basica(client):
    response = client.get("/api/llm/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] in {"ollama", "unsupported"}
    assert "force_deterministic" in payload
    if payload["provider"] == "ollama":
        assert "timeouts" in payload
        assert "keep_alive" in payload
        assert "warmup_enabled" in payload
        assert "last_warmup" in payload

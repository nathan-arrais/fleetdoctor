def test_chat_session_and_ask_flow(client):
    create_response = client.post("/api/chat/sessions", json={"title": "Sessao teste"})
    assert create_response.status_code == 200
    session = create_response.json()
    session_id = session["id"]
    assert session["title"] == "Sessao teste"

    sessions_response = client.get("/api/chat/sessions")
    assert sessions_response.status_code == 200
    sessions = sessions_response.json()
    assert any(item["id"] == session_id for item in sessions)

    empty_messages = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert empty_messages.status_code == 200
    assert empty_messages.json() == []

    ask_response = client.post(
        "/api/chat/ask",
        json={
            "session_id": session_id,
            "message": "Quais os principais riscos da semana?",
            "force_deterministic": True,
        },
    )
    assert ask_response.status_code == 200
    payload = ask_response.json()
    assert payload["session_id"] == session_id
    assert payload["answer"]
    assert payload["source"] == "deterministic_fallback"
    assert payload["user_message"]["role"] == "user"
    assert payload["assistant_message"]["role"] == "assistant"

    messages_response = client.get(f"/api/chat/sessions/{session_id}/messages")
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_chat_ask_sessao_inexistente(client):
    response = client.post(
        "/api/chat/ask",
        json={
            "session_id": 999999,
            "message": "Teste de sessao invalida",
        },
    )
    assert response.status_code == 404

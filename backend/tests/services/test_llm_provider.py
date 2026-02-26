import pytest

from app.services.llm_provider import LLMSettings, OllamaProvider


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, *, get_payload=None, post_payloads=None, captured_posts=None):
        self.get_payload = get_payload or {"models": []}
        self.post_payloads = list(post_payloads or [])
        self.captured_posts = captured_posts if captured_posts is not None else []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, _url):
        return _FakeResponse(self.get_payload)

    def post(self, _url, json):
        self.captured_posts.append(json)
        if self.post_payloads:
            return _FakeResponse(self.post_payloads.pop(0))
        return _FakeResponse({"response": "ok", "model": json.get("model")})


def test_generate_envia_keep_alive(monkeypatch):
    captured_posts = []
    fake_client = _FakeClient(captured_posts=captured_posts, post_payloads=[{"response": "ok", "model": "qwen2.5:7b"}])
    provider = OllamaProvider(LLMSettings(keep_alive="20m"))
    monkeypatch.setattr(provider, "_available_models", lambda: [])
    monkeypatch.setattr(provider, "_client", lambda: fake_client)

    result = provider.generate("system", "user")

    assert result["text"] == "ok"
    assert captured_posts
    assert captured_posts[0]["keep_alive"] == "20m"


def test_generate_retorna_erro_quando_modelos_entregam_resposta_vazia(monkeypatch):
    fake_client = _FakeClient(
        post_payloads=[
            {"response": "   ", "model": "qwen2.5:7b"},
            {"response": "", "model": "llama3.1:8b"},
        ]
    )
    provider = OllamaProvider(LLMSettings(primary_model="qwen2.5:7b", fallback_model="llama3.1:8b"))
    monkeypatch.setattr(provider, "_available_models", lambda: [])
    monkeypatch.setattr(provider, "_client", lambda: fake_client)

    with pytest.raises(RuntimeError) as exc_info:
        provider.generate("system", "user")
    text = str(exc_info.value)
    assert "Todas as tentativas com Ollama falharam" in text
    assert "Resposta vazia do modelo" in text


def test_warmup_respeita_modo_force_deterministic():
    settings = LLMSettings(force_deterministic=True, warmup_on_startup=True)
    provider = OllamaProvider(settings)

    report = provider.warmup()

    assert report["enabled"] is True
    assert report["skipped"] is True
    assert "FORCE_DETERMINISTIC" in report["reason"]


def test_health_expoe_timeout_e_warmup(monkeypatch):
    fake_client = _FakeClient(get_payload={"models": [{"name": "qwen2.5:7b"}]})
    settings = LLMSettings(
        timeout_ms=30000,
        connect_timeout_ms=2000,
        read_timeout_ms=30000,
        keep_alive="10m",
        warmup_on_startup=True,
    )
    provider = OllamaProvider(settings)
    monkeypatch.setattr(provider, "_client", lambda: fake_client)

    payload = provider.health()

    assert payload["provider"] == "ollama"
    assert payload["reachable"] is True
    assert payload["keep_alive"] == "10m"
    assert payload["warmup_enabled"] is True
    assert payload["timeouts"]["overall_ms"] == 30000
    assert payload["timeouts"]["connect_ms"] == 2000
    assert payload["timeouts"]["read_ms"] == 30000

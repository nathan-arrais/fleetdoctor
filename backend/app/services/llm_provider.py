import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class LLMSettings:
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "ollama"))
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    primary_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL_PRIMARY", "qwen2.5:7b"))
    fallback_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL_FALLBACK", "llama3.1:8b"))
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.2")))
    top_p: float = field(default_factory=lambda: float(os.getenv("LLM_TOP_P", "0.9")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "500")))
    timeout_ms: int = field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT_MS", "30000")))
    connect_timeout_ms: int = field(default_factory=lambda: int(os.getenv("LLM_CONNECT_TIMEOUT_MS", "2000")))
    read_timeout_ms: int = field(default_factory=lambda: int(os.getenv("LLM_READ_TIMEOUT_MS", "30000")))
    keep_alive: str = field(default_factory=lambda: os.getenv("OLLAMA_KEEP_ALIVE", "10m"))
    warmup_on_startup: bool = field(default_factory=lambda: _as_bool(os.getenv("LLM_WARMUP_ON_STARTUP"), default=True))
    retry_json_invalid: int = field(default_factory=lambda: int(os.getenv("LLM_RETRY_JSON_INVALID", "1")))
    force_deterministic: bool = field(
        default_factory=lambda: _as_bool(os.getenv("LLM_FORCE_DETERMINISTIC"), default=False)
    )


_last_warmup_report: dict[str, Any] | None = None


class OllamaProvider:
    def __init__(self, settings: LLMSettings):
        self.settings = settings

    def _client(self) -> httpx.Client:
        overall_timeout = max(self.settings.timeout_ms, 200) / 1000
        connect_timeout = max(self.settings.connect_timeout_ms, 200) / 1000
        read_timeout = max(self.settings.read_timeout_ms, 200) / 1000
        timeout = httpx.Timeout(timeout=overall_timeout, connect=connect_timeout, read=read_timeout)
        return httpx.Client(timeout=timeout)

    def _available_models(self) -> list[str]:
        base = self.settings.ollama_base_url.rstrip("/")
        try:
            with self._client() as client:
                response = client.get(f"{base}/api/tags")
                response.raise_for_status()
                data = response.json()
            return [item.get("name", "") for item in data.get("models", []) if item.get("name")]
        except Exception:
            return []

    def _models(self, preferred_model: str | None = None) -> list[str]:
        models: list[str] = []
        if preferred_model:
            models.append(preferred_model)
        models.extend([self.settings.primary_model, self.settings.fallback_model])
        deduped: list[str] = []
        for model in models:
            if model and model not in deduped:
                deduped.append(model)
        return deduped

    def health(self) -> dict[str, Any]:
        base = self.settings.ollama_base_url.rstrip("/")
        available_models: list[str] = []
        reachable = False
        error_message: str | None = None

        try:
            with self._client() as client:
                response = client.get(f"{base}/api/tags")
                response.raise_for_status()
                data = response.json()
                available_models = [item.get("name", "") for item in data.get("models", []) if item.get("name")]
                reachable = True
        except Exception as exc:
            error_message = str(exc)

        return {
            "provider": "ollama",
            "base_url": base,
            "reachable": reachable,
            "primary_model": self.settings.primary_model,
            "fallback_model": self.settings.fallback_model,
            "available_models": available_models,
            "force_deterministic": self.settings.force_deterministic,
            "timeouts": {
                "overall_ms": self.settings.timeout_ms,
                "connect_ms": self.settings.connect_timeout_ms,
                "read_ms": self.settings.read_timeout_ms,
            },
            "keep_alive": self.settings.keep_alive,
            "warmup_enabled": self.settings.warmup_on_startup,
            "last_warmup": _last_warmup_report,
            "error": error_message,
        }

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        preferred_model: str | None = None,
    ) -> dict[str, Any]:
        base = self.settings.ollama_base_url.rstrip("/")
        model_errors: list[str] = []
        models = self._models(preferred_model=preferred_model)
        available_models = self._available_models()
        if available_models:
            configured_available = [model for model in models if model in available_models]
            if configured_available:
                models = configured_available
            else:
                models = [available_models[0], *models]

        for model in models:
            request_started = time.perf_counter()
            try:
                payload = {
                    "model": model,
                    "system": system_prompt,
                    "prompt": user_prompt,
                    "stream": False,
                    "keep_alive": self.settings.keep_alive,
                    "options": {
                        "temperature": self.settings.temperature,
                        "top_p": self.settings.top_p,
                        "num_predict": self.settings.max_tokens,
                    },
                }
                with self._client() as client:
                    response = client.post(f"{base}/api/generate", json=payload)
                    response.raise_for_status()
                    data = response.json()
                elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                text = str(data.get("response", "")).strip()
                if not text:
                    raise ValueError("Resposta vazia do modelo")
                return {
                    "text": text,
                    "model": data.get("model", model),
                    "latency_ms": elapsed_ms,
                }
            except Exception as exc:
                model_errors.append(f"{model}: {exc}")

        raise RuntimeError("Todas as tentativas com Ollama falharam: " + " | ".join(model_errors))

    def warmup(self) -> dict[str, Any]:
        global _last_warmup_report

        started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        if not self.settings.warmup_on_startup:
            report = {
                "started_at": started_at,
                "finished_at": started_at,
                "enabled": False,
                "skipped": True,
                "reason": "Warmup desabilitado por configuracao",
                "results": [],
            }
            _last_warmup_report = report
            return report

        if self.settings.force_deterministic:
            report = {
                "started_at": started_at,
                "finished_at": started_at,
                "enabled": True,
                "skipped": True,
                "reason": "LLM_FORCE_DETERMINISTIC habilitado",
                "results": [],
            }
            _last_warmup_report = report
            return report

        base = self.settings.ollama_base_url.rstrip("/")
        results: list[dict[str, Any]] = []
        for model in self._models():
            request_started = time.perf_counter()
            try:
                payload = {
                    "model": model,
                    "prompt": "Responda apenas com: ok",
                    "stream": False,
                    "keep_alive": self.settings.keep_alive,
                    "options": {
                        "temperature": 0.0,
                        "top_p": 1.0,
                        "num_predict": 8,
                    },
                }
                with self._client() as client:
                    response = client.post(f"{base}/api/generate", json=payload)
                    response.raise_for_status()
                    data = response.json()
                elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                text = str(data.get("response", "")).strip()
                if not text:
                    raise ValueError("Resposta vazia do modelo")
                results.append({"model": model, "ok": True, "latency_ms": elapsed_ms, "error": None})
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                results.append({"model": model, "ok": False, "latency_ms": elapsed_ms, "error": str(exc)})

        finished_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        report = {
            "started_at": started_at,
            "finished_at": finished_at,
            "enabled": True,
            "skipped": False,
            "reason": None,
            "results": results,
        }
        _last_warmup_report = report
        return report

import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterable

import httpx


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _dedupe(items: Iterable[str]) -> list[str]:
    output: list[str] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def _classify_error(exc: Exception) -> str:
    if isinstance(exc, (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException)):
        return "timeout"
    if isinstance(exc, httpx.NetworkError):
        return "network"
    text = str(exc).lower()
    if "resposta vazia" in text:
        return "empty_response"
    if "json" in text:
        return "json_invalid"
    return "unknown"


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


def build_chat_llm_settings(base_settings: LLMSettings | None = None) -> LLMSettings:
    base = base_settings or LLMSettings()
    chat_timeout = int(os.getenv("LLM_CHAT_TIMEOUT_MS", "90000"))
    return LLMSettings(
        provider=base.provider,
        ollama_base_url=base.ollama_base_url,
        primary_model=os.getenv("OLLAMA_CHAT_MODEL_PRIMARY", "qwen3:4b"),
        fallback_model=os.getenv("OLLAMA_CHAT_MODEL_FALLBACK", "qwen2.5:7b"),
        temperature=float(os.getenv("LLM_CHAT_TEMPERATURE", str(base.temperature))),
        top_p=float(os.getenv("LLM_CHAT_TOP_P", str(base.top_p))),
        max_tokens=int(os.getenv("LLM_CHAT_MAX_TOKENS", "220")),
        timeout_ms=chat_timeout,
        connect_timeout_ms=int(os.getenv("LLM_CHAT_CONNECT_TIMEOUT_MS", str(base.connect_timeout_ms))),
        read_timeout_ms=int(os.getenv("LLM_CHAT_READ_TIMEOUT_MS", str(chat_timeout))),
        keep_alive=os.getenv("OLLAMA_CHAT_KEEP_ALIVE", base.keep_alive),
        warmup_on_startup=base.warmup_on_startup,
        retry_json_invalid=int(os.getenv("LLM_CHAT_RETRY_JSON_INVALID", "1")),
        force_deterministic=base.force_deterministic,
    )


class LLMGenerationError(RuntimeError):
    def __init__(self, message: str, *, attempts: list[dict[str, Any]]):
        super().__init__(message)
        self.attempts = attempts


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
        return _dedupe(models)

    def health(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
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

        payload = {
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
            "max_tokens": self.settings.max_tokens,
            "keep_alive": self.settings.keep_alive,
            "warmup_enabled": self.settings.warmup_on_startup,
            "last_warmup": _last_warmup_report,
            "error": error_message,
        }
        if extra:
            payload.update(extra)
        return payload

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        preferred_model: str | None = None,
        max_model_attempts: int | None = None,
        excluded_models: set[str] | None = None,
    ) -> dict[str, Any]:
        base = self.settings.ollama_base_url.rstrip("/")
        models = self._models(preferred_model=preferred_model)
        available_models = self._available_models()
        if available_models:
            configured_available = [model for model in models if model in available_models]
            if configured_available:
                models = configured_available
            else:
                models = [available_models[0], *models]

        if excluded_models:
            models = [model for model in models if model not in excluded_models]
        models = _dedupe(models)

        if max_model_attempts is not None and max_model_attempts > 0:
            models = models[:max_model_attempts]

        if not models:
            raise LLMGenerationError(
                "Nenhum modelo disponivel para tentativa no Ollama",
                attempts=[],
            )

        model_errors: list[str] = []
        attempts: list[dict[str, Any]] = []
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

                attempts.append(
                    {
                        "model": data.get("model", model),
                        "ok": True,
                        "latency_ms": elapsed_ms,
                        "error": None,
                        "error_type": None,
                    }
                )
                return {
                    "text": text,
                    "model": data.get("model", model),
                    "latency_ms": elapsed_ms,
                    "attempts": attempts,
                }
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                error_type = _classify_error(exc)
                attempts.append(
                    {
                        "model": model,
                        "ok": False,
                        "latency_ms": elapsed_ms,
                        "error": str(exc),
                        "error_type": error_type,
                    }
                )
                model_errors.append(f"{model}: {exc}")

        raise LLMGenerationError(
            "Todas as tentativas com Ollama falharam: " + " | ".join(model_errors),
            attempts=attempts,
        )

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

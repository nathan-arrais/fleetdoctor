import os
import time
from dataclasses import dataclass, field
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
    primary_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL_PRIMARY", "qwen2.5:7b-instruct"))
    fallback_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL_FALLBACK", "llama3.1:8b-instruct-q4_K_M"))
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.2")))
    top_p: float = field(default_factory=lambda: float(os.getenv("LLM_TOP_P", "0.9")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "500")))
    timeout_ms: int = field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT_MS", "6000")))
    force_deterministic: bool = field(
        default_factory=lambda: _as_bool(os.getenv("LLM_FORCE_DETERMINISTIC"), default=False)
    )


class OllamaProvider:
    def __init__(self, settings: LLMSettings):
        self.settings = settings

    def _client(self) -> httpx.Client:
        timeout = max(self.settings.timeout_ms, 200) / 1000
        return httpx.Client(timeout=timeout)

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

        for model in models:
            request_started = time.perf_counter()
            try:
                payload = {
                    "model": model,
                    "system": system_prompt,
                    "prompt": user_prompt,
                    "stream": False,
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
                return {
                    "text": data.get("response", ""),
                    "model": data.get("model", model),
                    "latency_ms": elapsed_ms,
                }
            except Exception as exc:
                model_errors.append(f"{model}: {exc}")

        raise RuntimeError("Todas as tentativas com Ollama falharam: " + " | ".join(model_errors))

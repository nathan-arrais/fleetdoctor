from fastapi import APIRouter

from ..services.llm_provider import LLMSettings, OllamaProvider, build_chat_llm_settings

router = APIRouter()


@router.get("/llm/health")
def llm_health():
    settings = LLMSettings()
    chat_settings = build_chat_llm_settings(settings)
    if settings.provider != "ollama":
        return {
            "provider": settings.provider,
            "reachable": False,
            "force_deterministic": settings.force_deterministic,
            "chat": {
                "primary_model": chat_settings.primary_model,
                "fallback_model": chat_settings.fallback_model,
                "timeout_ms": chat_settings.timeout_ms,
                "max_tokens": chat_settings.max_tokens,
                "retry_json_invalid": chat_settings.retry_json_invalid,
            },
            "error": "Provider nao suportado nesta versao",
        }
    return OllamaProvider(settings).health(
        extra={
            "chat": {
                "primary_model": chat_settings.primary_model,
                "fallback_model": chat_settings.fallback_model,
                "timeout_ms": chat_settings.timeout_ms,
                "max_tokens": chat_settings.max_tokens,
                "retry_json_invalid": chat_settings.retry_json_invalid,
            }
        }
    )

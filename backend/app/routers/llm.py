from fastapi import APIRouter

from ..services.llm_provider import LLMSettings, OllamaProvider

router = APIRouter()


@router.get("/llm/health")
def llm_health():
    settings = LLMSettings()
    if settings.provider != "ollama":
        return {
            "provider": settings.provider,
            "reachable": False,
            "force_deterministic": settings.force_deterministic,
            "error": "Provider nao suportado nesta versao",
        }
    return OllamaProvider(settings).health()

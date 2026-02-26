import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - fallback para ambientes sem python-dotenv instalado
    def load_dotenv(*_args, **_kwargs):
        return False
from .db import Base, engine, ensure_schema_compatibility
from .routers import health, dashboard, triage, vehicles, trips, diagnosis, reports, upload, llm, chat
from .services.llm_provider import LLMSettings, OllamaProvider, build_chat_llm_settings


def _load_backend_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        print(f"[config] .env carregado de {env_path}")
    else:
        print("[config] arquivo backend/.env não encontrado; usando variaveis de ambiente do processo")


_load_backend_env_file()


def _dedupe_models(models: list[str]) -> list[str]:
    deduped: list[str] = []
    for model in models:
        if model and model not in deduped:
            deduped.append(model)
    return deduped


def _build_warmup_settings(base: LLMSettings, chat: LLMSettings) -> LLMSettings:
    # Warmup precisa de timeout mais alto para reduzir cold start seguido de fallback no primeiro uso.
    warmup_timeout_ms = max(base.timeout_ms, base.read_timeout_ms, chat.timeout_ms, chat.read_timeout_ms, 90000)
    warmup_connect_ms = max(base.connect_timeout_ms, chat.connect_timeout_ms)
    return LLMSettings(
        provider=base.provider,
        ollama_base_url=base.ollama_base_url,
        primary_model=base.primary_model,
        fallback_model=base.fallback_model,
        temperature=base.temperature,
        top_p=base.top_p,
        max_tokens=base.max_tokens,
        timeout_ms=warmup_timeout_ms,
        connect_timeout_ms=warmup_connect_ms,
        read_timeout_ms=warmup_timeout_ms,
        keep_alive=chat.keep_alive or base.keep_alive,
        disable_thinking=chat.disable_thinking,
        warmup_on_startup=base.warmup_on_startup,
        retry_json_invalid=base.retry_json_invalid,
        force_deterministic=base.force_deterministic,
    )


def _run_ollama_warmup() -> None:
    settings = LLMSettings()
    chat_settings = build_chat_llm_settings(settings)
    print(
        "[llm/config] provider=%s base=%s chat_primary=%s chat_fallback=%s chat_timeout_ms=%s chat_max_tokens=%s chat_retry=%s chat_disable_thinking=%s"
        % (
            settings.provider,
            settings.ollama_base_url,
            chat_settings.primary_model,
            chat_settings.fallback_model,
            chat_settings.timeout_ms,
            chat_settings.max_tokens,
            chat_settings.retry_json_invalid,
            chat_settings.disable_thinking,
        )
    )
    if settings.provider != "ollama":
        return
    try:
        warmup_settings = _build_warmup_settings(settings, chat_settings)
        warmup_models = _dedupe_models(
            [
                settings.primary_model,
                settings.fallback_model,
                chat_settings.primary_model,
                chat_settings.fallback_model,
            ]
        )
        report = OllamaProvider(warmup_settings).warmup(models=warmup_models)
        if report.get("skipped"):
            print(f"[llm/warmup] skipped: {report.get('reason')}")
            return
        total_ok = len([item for item in report.get("results", []) if item.get("ok")])
        total_models = len(report.get("results", []))
        print(
            "[llm/warmup] concluído: %s/%s modelos aquecidos (%s)"
            % (total_ok, total_models, ", ".join(report.get("models", [])))
        )
    except Exception as exc:
        print(f"[llm/warmup] falhou sem bloquear startup: {exc}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _run_ollama_warmup()
    yield


app = FastAPI(title="FleetDoctor API", version="0.1.0", lifespan=lifespan)

cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
allow_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
ensure_schema_compatibility(engine)

app.include_router(health.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(triage.router, prefix="/api")
app.include_router(vehicles.router, prefix="/api")
app.include_router(trips.router, prefix="/api")
app.include_router(diagnosis.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(llm.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

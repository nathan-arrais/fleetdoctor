import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import Base, engine, ensure_schema_compatibility
from .routers import health, dashboard, triage, vehicles, trips, diagnosis, reports, upload, llm, chat

app = FastAPI(title="FleetDoctor API", version="0.1.0")

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

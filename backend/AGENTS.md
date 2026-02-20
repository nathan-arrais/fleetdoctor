# Repository Guidelines

## Project Structure & Module Organization
- Backend code lives in `backend/app/` (FastAPI + SQLAlchemy + SQLite).
- Frontend code lives in `frontend/src/` (React + Vite + TypeScript).
- Routers: `backend/app/routers/`; shared logic: `backend/app/services/`.
- Data model and contracts: `backend/app/models.py`, `backend/app/schemas.py`.
- Runtime artifacts (`backend/app/fleetdoctor.db`, `backend/app/reports_store/`) are generated outputs, not source.

## Build, Test, and Development Commands
- Create and activate venv (Windows PowerShell):
  - `python -m venv .venv`
  - `.\.venv\Scripts\activate`
- Backend deps: `pip install -r backend/requirements.txt`
- Frontend deps: `cd frontend && npm install`
- Seed demo data: `cd backend && python -m app.seed`
- Run API: `cd backend && uvicorn app.main:app --reload`
- Run frontend: `cd frontend && npm run dev`
- Quick API smoke test: `curl http://localhost:8000/api/health`

## Coding Style & Naming Conventions
- Follow PEP 8 with 4-space indentation and clear type hints.
- Use `snake_case` for functions/variables/modules, `PascalCase` for classes and Pydantic/ORM models.
- Keep routers thin: request parsing and response shaping in `app/routers/`, reusable logic in `app/services/`.
- Prefer explicit schema names with suffixes like `*Out`, `*Request`, `*Response` (see `app/schemas.py`).

## Testing Guidelines
- Current repository state has no committed automated test suite; add tests with new features/fixes.
- Place tests under `tests/` mirroring source modules (example: `tests/routers/test_health.py`).
- Focus on endpoint behavior, upload edge cases, and report filtering.
- For API tests, use FastAPI `TestClient` and deterministic fixtures.
- Minimum manual checks for backend changes:
  - `POST /api/upload/import` with CSV containing BOM and mixed-case enums.
  - report generation with date-only vs datetime `end`.

## Commit & Pull Request Guidelines
- Local snapshot does not include `.git` history, so no enforced legacy commit format is discoverable.
- Use concise Conventional Commit-style messages (example: `feat(upload): validate required CSV columns`).
- PRs should include: objective, affected endpoints/files, test evidence (commands + results), and sample request/response for API changes.
- Link related issue/task IDs and note any DB/reset/report-store side effects.

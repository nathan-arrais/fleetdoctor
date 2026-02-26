import shutil
from pathlib import Path

from sqlalchemy import create_engine

from app.db import ensure_schema_compatibility


def _create_legacy_chat_table(db_url: str) -> None:
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE chat_messages (
                id INTEGER PRIMARY KEY,
                session_id INTEGER,
                role TEXT,
                content TEXT,
                created_at TEXT,
                source TEXT,
                model TEXT,
                latency_ms INTEGER,
                used_tools_json TEXT,
                fallback_reason TEXT,
                validation_warnings_json TEXT
            )
            """
        )


def _get_columns(db_url: str) -> set[str]:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(chat_messages)").fetchall()
    return {str(row[1]) for row in rows}


def _schema_runtime_dir() -> Path:
    path = Path("tests_runtime_schema")
    path.mkdir(exist_ok=True)
    return path


def test_schema_compatibility_adds_missing_chat_columns():
    runtime_dir = _schema_runtime_dir()
    try:
        db_path = runtime_dir / "legacy_chat.db"
        if db_path.exists():
            db_path.unlink()
        db_url = f"sqlite:///{db_path.as_posix()}"
        _create_legacy_chat_table(db_url)

        engine = create_engine(db_url)
        ensure_schema_compatibility(engine)

        columns = _get_columns(db_url)
        assert "citations_json" in columns
        assert "follow_up_questions_json" in columns
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)


def test_schema_compatibility_is_idempotent():
    runtime_dir = _schema_runtime_dir()
    try:
        db_path = runtime_dir / "legacy_chat_idempotent.db"
        if db_path.exists():
            db_path.unlink()
        db_url = f"sqlite:///{db_path.as_posix()}"
        _create_legacy_chat_table(db_url)

        engine = create_engine(db_url)
        ensure_schema_compatibility(engine)
        ensure_schema_compatibility(engine)

        columns = _get_columns(db_url)
        assert "citations_json" in columns
        assert "follow_up_questions_json" in columns
    finally:
        shutil.rmtree(runtime_dir, ignore_errors=True)

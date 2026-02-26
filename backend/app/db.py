import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "fleetdoctor.db"
DB_PATH = str(Path(os.getenv("FLEETDOCTOR_DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve())
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{Path(DB_PATH).as_posix()}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def _sqlite_table_exists(bind_engine: Engine, table_name: str) -> bool:
    query = "SELECT name FROM sqlite_master WHERE type='table' AND name = ?"
    with bind_engine.connect() as conn:
        row = conn.exec_driver_sql(query, (table_name,)).first()
    return row is not None


def _sqlite_table_columns(bind_engine: Engine, table_name: str) -> set[str]:
    with bind_engine.connect() as conn:
        rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def ensure_schema_compatibility(bind_engine: Engine) -> None:
    if bind_engine.dialect.name != "sqlite":
        return

    table_name = "chat_messages"
    if not _sqlite_table_exists(bind_engine, table_name):
        return

    required_columns = {
        "citations_json": "TEXT",
        "follow_up_questions_json": "TEXT",
    }
    existing_columns = _sqlite_table_columns(bind_engine, table_name)

    with bind_engine.begin() as conn:
        for column_name, column_type in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )

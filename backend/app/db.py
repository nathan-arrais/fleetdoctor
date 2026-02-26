import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "fleetdoctor.db"
DB_PATH = str(Path(os.getenv("FLEETDOCTOR_DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve())
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{Path(DB_PATH).as_posix()}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass

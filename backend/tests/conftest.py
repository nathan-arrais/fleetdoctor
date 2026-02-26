import os
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _reload_app_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            sys.modules.pop(module_name)


@pytest.fixture(scope="session")
def client() -> TestClient:
    runtime_dir = Path("tests_runtime")
    reports_dir = runtime_dir / "reports"
    db_path = runtime_dir / "fleetdoctor_test.db"

    runtime_dir.mkdir(exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    if reports_dir.exists():
        shutil.rmtree(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    os.environ["FLEETDOCTOR_DB_PATH"] = str(db_path)
    os.environ["REPORTS_DIR"] = str(reports_dir)

    _reload_app_modules()
    from app.seed import seed
    from app.main import app

    seed()
    with TestClient(app) as test_client:
        yield test_client

    os.environ.pop("FLEETDOCTOR_DB_PATH", None)
    os.environ.pop("REPORTS_DIR", None)
    shutil.rmtree(runtime_dir, ignore_errors=True)
    _reload_app_modules()

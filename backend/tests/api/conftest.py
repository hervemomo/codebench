from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from tests.db.conftest import _alembic_config

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="session", autouse=True)
def _schema_at_head():
    command.upgrade(_alembic_config(), "head")
    yield


@pytest.fixture(autouse=True)
def _test_settings(monkeypatch):
    """RQ jobs execute inline (no worker process needed); LLM calls use the
    deterministic fake client (no real API key needed)."""
    monkeypatch.setenv("RQ_IS_ASYNC", "false")
    monkeypatch.setenv("FAKE_LLM", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client():
    """Bare, unauthenticated client — fresh cookie jar per test."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def make_client():
    """Factory: make_client() -> (authenticated TestClient, user dict).

    Each call registers a brand-new org + admin user, so tests that need two
    independent identities (cross-org tests) just call it twice.
    """
    def _make(email=None, password="Password123!", org_name=None):
        c = TestClient(app)
        suffix = uuid4().hex[:10]
        email = email or f"user-{suffix}@example.com"
        org_name = org_name or f"Org-{suffix}"
        resp = c.post("/api/auth/register", json={"email": email, "password": password, "org_name": org_name})
        assert resp.status_code == 201, resp.text
        return c, resp.json()

    return _make


@pytest.fixture()
def tiny_survey_bytes():
    return (DATA_DIR / "tiny_survey.xlsx").read_bytes()

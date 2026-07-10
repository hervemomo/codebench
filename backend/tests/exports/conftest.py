from uuid import uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.base import SessionLocal
from app.main import app
from app.models import Dataset, Question, Response
from tests.db.conftest import _alembic_config


@pytest.fixture(scope="session", autouse=True)
def _schema_at_head():
    command.upgrade(_alembic_config(), "head")
    yield


@pytest.fixture(autouse=True)
def _test_settings(monkeypatch):
    monkeypatch.setenv("RQ_IS_ASYNC", "false")
    monkeypatch.setenv("FAKE_LLM", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def make_client():
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
def seed_dataset(make_client):
    """Factory: seed_dataset(texts) -> dict with an authenticated client plus a
    dataset whose Response rows carry exactly the given texts. Bypasses
    upload/preprocess (covered by Sequence 3) for deterministic input text."""
    def _seed(texts: list[str], *, survey_context="Consumers of a beverage brand describe what they like about it."):
        client, user = make_client()
        org_id = user["org_id"]

        project = client.post("/api/projects", json={
            "name": "P", "context": survey_context, "source_lang": "en", "target_lang": "en", "codebook_lang": "en",
        }).json()
        question = client.post(f"/api/projects/{project['id']}/questions", json={"text": "Q", "survey_col": "feedback"}).json()

        session = SessionLocal()
        try:
            db_question = session.get(Question, question["id"])
            dataset = Dataset(org_id=org_id, question_id=db_question.id, file_key="datasets/seeded.xlsx", sheet="0", status="preprocessed")
            session.add(dataset)
            session.flush()
            for text in texts:
                session.add(Response(org_id=org_id, dataset_id=dataset.id, raw_text=text, clean_text=text, translated_text=text, is_valid=True))
            session.commit()
            dataset_id = dataset.id
        finally:
            session.close()

        return {"client": client, "user": user, "project_id": project["id"], "question_id": question["id"], "dataset_id": dataset_id}

    return _seed


@pytest.fixture()
def build_applied_run(seed_dataset):
    """seed_dataset(texts) -> import `codebook_source` as codes, accept all,
    finalize, apply. Returns seed_dataset's dict plus "run_id"."""
    def _build(texts: list[str], codebook_source: list):
        seeded = seed_dataset(texts)
        client = seeded["client"]
        run_id = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
            "kind": "import", "codebook_source": codebook_source,
        }).json()["id"]

        codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
        for c in codes:
            client.patch(f"/api/runs/{run_id}/codes/{c['code_id']}", json={"status": "accepted"})
        finalize_resp = client.post(f"/api/runs/{run_id}/finalize")
        assert finalize_resp.status_code == 200, finalize_resp.text
        apply_resp = client.post(f"/api/runs/{run_id}/apply")
        assert apply_resp.status_code == 202, apply_resp.text

        seeded["run_id"] = run_id
        return seeded

    return _build

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.base import SessionLocal
from app.main import app
from app.models import Dataset, Question, Response
from codeframe.config import PreprocessConfig
from codeframe.preprocessing import load_survey_data, preprocess as codeframe_preprocess
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
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def make_client():
    """Factory: make_client() -> (authenticated TestClient, user dict)."""
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
    dataset whose Response rows carry exactly the given texts (translated_text
    == text, is_valid=True). Bypasses upload/preprocess entirely -- those are
    already covered by Sequence 3 -- so coding-stage tests get fully
    deterministic input text for the fake LLM's keyword-based matching.
    """
    def _seed(texts: list[str], *, source_lang="en", target_lang="en", codebook_lang="en", survey_context="Open-ended survey responses about a product."):
        client, user = make_client()
        org_id = user["org_id"]

        project = client.post("/api/projects", json={
            "name": "P", "context": survey_context,
            "source_lang": source_lang, "target_lang": target_lang, "codebook_lang": codebook_lang,
        }).json()
        question = client.post(f"/api/projects/{project['id']}/questions", json={"text": "Q", "survey_col": "feedback"}).json()

        session = SessionLocal()
        try:
            db_question = session.get(Question, question["id"])
            assert db_question is not None
            dataset = Dataset(org_id=org_id, question_id=db_question.id, file_key="datasets/seeded.xlsx", sheet="0", status="preprocessed")
            session.add(dataset)
            session.flush()
            for text in texts:
                session.add(Response(
                    org_id=org_id, dataset_id=dataset.id,
                    raw_text=text, clean_text=text, translated_text=text, is_valid=True,
                ))
            session.commit()
            dataset_id = dataset.id
        finally:
            session.close()

        return {"client": client, "user": user, "project_id": project["id"], "question_id": question["id"], "dataset_id": dataset_id}

    return _seed


@pytest.fixture()
def tiny_survey_texts():
    """The 30 kept, cleaned texts from tests/data/tiny_survey.xlsx -- the same
    corpus tests/codeframe/test_demo.py already proves clusters into 3-7
    themes via FakeOpenAI's keyword-based embeddings."""
    df = load_survey_data(DATA_DIR / "tiny_survey.xlsx", "feedback")
    result = codeframe_preprocess(df, PreprocessConfig())
    return result.kept["cleaned_text"].tolist()


@pytest.fixture()
def seed_tiny_survey_dataset(seed_dataset, tiny_survey_texts):
    """seed_dataset() pre-loaded with the proven tiny_survey.xlsx corpus --
    for kind="ai" tests, which need >=10 responses for clustering."""
    def _seed():
        return seed_dataset(tiny_survey_texts, survey_context="Consumers of a beverage brand describe what they like about it.")

    return _seed

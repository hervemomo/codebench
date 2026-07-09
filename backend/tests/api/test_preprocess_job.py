"""RQ job runs synchronously (RQ_IS_ASYNC=false, set by the autouse
_test_settings fixture) with the fake LLM. Asserts Response rows are created
and the stats endpoint matches Sequence-1's codeframe package results exactly.
"""

from codeframe.config import PreprocessConfig
from codeframe.preprocessing import load_survey_data, preprocess as codeframe_preprocess


def _setup_dataset(client, tiny_survey_bytes) -> dict:
    project = client.post("/api/projects", json={"name": "P", "source_lang": "en", "target_lang": "en"}).json()
    question = client.post(f"/api/projects/{project['id']}/questions", json={"text": "Q", "survey_col": "feedback"}).json()
    return client.post(
        f"/api/questions/{question['id']}/datasets",
        files={"file": ("tiny_survey.xlsx", tiny_survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    ).json()


def test_preprocess_job_runs_synchronously_and_finishes(make_client, tiny_survey_bytes):
    client, _ = make_client()
    dataset = _setup_dataset(client, tiny_survey_bytes)

    resp = client.post(f"/api/datasets/{dataset['id']}/preprocess")
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "finished"
    assert job["stage"] == "done"


def test_preprocess_job_creates_response_rows_and_updates_dataset_status(make_client, tiny_survey_bytes):
    client, _ = make_client()
    dataset = _setup_dataset(client, tiny_survey_bytes)

    job_id = client.post(f"/api/datasets/{dataset['id']}/preprocess").json()["job_id"]
    client.get(f"/api/jobs/{job_id}")  # ensure it's been fetched at least once

    stats = client.get(f"/api/datasets/{dataset['id']}/stats").json()
    assert stats["total"] > 0
    assert stats["kept"] > 0


def test_preprocess_stats_match_codeframe_package_exactly(make_client, tiny_survey_bytes):
    client, _ = make_client()
    dataset = _setup_dataset(client, tiny_survey_bytes)
    client.post(f"/api/datasets/{dataset['id']}/preprocess")

    stats = client.get(f"/api/datasets/{dataset['id']}/stats").json()

    df = load_survey_data("tests/data/tiny_survey.xlsx", "feedback")
    expected = codeframe_preprocess(df, PreprocessConfig())

    assert stats["kept"] == len(expected.kept)
    assert stats["invalid"] == len(expected.invalid)
    assert stats["duplicates"] == len(expected.duplicates)
    assert stats["total"] == len(expected.kept) + len(set(expected.invalid.index) | set(expected.duplicates.index))


def test_preprocess_job_is_idempotent_on_rerun(make_client, tiny_survey_bytes):
    """Re-running preprocess (retry, worker restart, deliberate re-run) must not
    duplicate Response rows — a named Sequence 3 success criterion."""
    client, _ = make_client()
    dataset = _setup_dataset(client, tiny_survey_bytes)

    client.post(f"/api/datasets/{dataset['id']}/preprocess")
    stats_first = client.get(f"/api/datasets/{dataset['id']}/stats").json()

    client.post(f"/api/datasets/{dataset['id']}/preprocess")
    stats_second = client.get(f"/api/datasets/{dataset['id']}/stats").json()

    assert stats_second["total"] == stats_first["total"]
    assert stats_second["kept"] == stats_first["kept"]

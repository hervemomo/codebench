import json


def _setup_and_run_preprocess(client, tiny_survey_bytes) -> str:
    project = client.post("/api/projects", json={"name": "P", "source_lang": "en", "target_lang": "en"}).json()
    question = client.post(f"/api/projects/{project['id']}/questions", json={"text": "Q", "survey_col": "feedback"}).json()
    dataset = client.post(
        f"/api/questions/{question['id']}/datasets",
        files={"file": ("tiny_survey.xlsx", tiny_survey_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    ).json()
    return client.post(f"/api/datasets/{dataset['id']}/preprocess").json()["job_id"]


def _read_sse_events(client, job_id):
    events = []
    with client.stream("GET", f"/api/jobs/{job_id}/stream") as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            events.append(json.loads(line[len("data:"):].strip()))
    return events


def test_sse_stream_emits_monotonically_increasing_current(make_client, tiny_survey_bytes):
    client, _ = make_client()
    job_id = _setup_and_run_preprocess(client, tiny_survey_bytes)

    events = _read_sse_events(client, job_id)

    currents = [e["current"] for e in events]
    assert len(currents) >= 2
    assert all(b > a for a, b in zip(currents, currents[1:]))
    assert events[-1]["stage"] == "done"


def test_sse_stream_ends_after_done_stage(make_client, tiny_survey_bytes):
    client, _ = make_client()
    job_id = _setup_and_run_preprocess(client, tiny_survey_bytes)

    events = _read_sse_events(client, job_id)

    assert sum(1 for e in events if e["stage"] == "done") == 1
    assert events[-1]["current"] == events[-1]["total"]


def test_sse_stream_requires_auth(client):
    resp = client.get("/api/jobs/some-job-id/stream")
    assert resp.status_code == 401

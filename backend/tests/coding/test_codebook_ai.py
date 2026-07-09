"""kind="ai": embed -> cluster -> generate_codebook, saved as a DRAFT run
with every code (including the catch-all) marked "proposed"."""


def test_ai_run_creates_draft_run_with_proposed_codes(seed_tiny_survey_dataset):
    seeded = seed_tiny_survey_dataset()
    client = seeded["client"]

    resp = client.post(f"/api/questions/{seeded['question_id']}/runs", json={"kind": "ai"})
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["id"]
    assert resp.json()["kind"] == "ai"

    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "draft"
    assert run["kind"] == "s2"  # CodingRunKind.S2 -- notebook section 2, AI-generated
    codes = run["codebook"]["codes"]
    assert len(codes) >= 1
    assert all(c["status"] == "proposed" for c in codes)
    assert all(c["code_id"] for c in codes)


def test_ai_run_respects_target_codes_cap(seed_tiny_survey_dataset):
    seeded = seed_tiny_survey_dataset()
    client = seeded["client"]

    resp = client.post(f"/api/questions/{seeded['question_id']}/runs", json={"kind": "ai", "target_codes": 3})
    run_id = resp.json()["id"]
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]

    # generate_codebook always appends the catch-all on top of the requested count.
    assert len(codes) == 4


def test_ai_run_without_preprocessed_dataset_returns_409(make_client):
    client, _ = make_client()
    project = client.post("/api/projects", json={"name": "P", "source_lang": "en", "target_lang": "en"}).json()
    question = client.post(f"/api/projects/{project['id']}/questions", json={"text": "Q", "survey_col": "feedback"}).json()

    resp = client.post(f"/api/questions/{question['id']}/runs", json={"kind": "ai"})
    assert resp.status_code == 409

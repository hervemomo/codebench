"""POST /api/runs/{id}/apply: codes only from the accepted set, one
CodeAssignment per (response, assigned code), token usage recorded, and
re-applying (retry / worker restart) must not duplicate assignments."""

from app.db.base import SessionLocal
from app.models import CodeAssignment

TASTE_TEXTS = ["The taste is delicious and sweet.", "I love the flavor.", "Tastes amazing.", "Very tasty and delicious."]
PRICE_TEXTS = ["Great value for the price.", "It's affordable and cheap.", "Good price point.", "Worth the cost."]
PACKAGING_TEXTS = ["I like the bottle design.", "Nice packaging and label.", "The can looks great.", "Packaging is stylish."]


def _build_reviewed_run(seed_dataset):
    seeded = seed_dataset(TASTE_TEXTS + PRICE_TEXTS + PACKAGING_TEXTS)
    client = seeded["client"]

    resp = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import",
        "codebook_source": ["Taste & Flavor", "Price & Value", "Packaging & Design", "Availability"],
    })
    run_id = resp.json()["id"]
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    availability_id = next(c["code_id"] for c in codes if c["name"] == "Availability")

    for c in codes:
        new_status = "rejected" if c["code_id"] == availability_id else "accepted"
        client.patch(f"/api/runs/{run_id}/codes/{c['code_id']}", json={"status": new_status})

    finalize_resp = client.post(f"/api/runs/{run_id}/finalize")
    assert finalize_resp.status_code == 200, finalize_resp.text
    return client, run_id, availability_id, len(TASTE_TEXTS + PRICE_TEXTS + PACKAGING_TEXTS)


def test_apply_codes_every_valid_response_and_records_token_usage(seed_dataset):
    client, run_id, _availability_id, n_responses = _build_reviewed_run(seed_dataset)

    resp = client.post(f"/api/runs/{run_id}/apply")
    assert resp.status_code == 202, resp.text
    job_id = resp.json()["job_id"]
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["status"] == "finished"
    assert job["stage"] == "done"

    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "applied"
    assert run["token_usage"]["calls"] > 0
    assert run["token_usage"]["total_tokens"] > 0

    qa = client.get(f"/api/runs/{run_id}/qa").json()
    assert qa["total_valid"] == n_responses
    assert qa["total_coded"] == n_responses  # catch-all fallback guarantees no uncoded response
    assert qa["uncoded_count"] == 0


def test_rejected_codes_are_never_assigned(seed_dataset):
    client, run_id, availability_id, _n = _build_reviewed_run(seed_dataset)
    client.post(f"/api/runs/{run_id}/apply")

    session = SessionLocal()
    try:
        assigned_code_ids = {row.code_id for row in session.query(CodeAssignment).filter_by(run_id=run_id).all()}
    finally:
        session.close()
    assert availability_id not in assigned_code_ids


def test_reapplying_is_idempotent(seed_dataset):
    client, run_id, _availability_id, n_responses = _build_reviewed_run(seed_dataset)

    client.post(f"/api/runs/{run_id}/apply")
    session = SessionLocal()
    try:
        first_count = session.query(CodeAssignment).filter_by(run_id=run_id).count()
    finally:
        session.close()

    # The run is now APPLIED; re-applying through the same endpoint is allowed
    # (retry / worker restart / deliberate re-run) and must not duplicate rows.
    resp = client.post(f"/api/runs/{run_id}/apply")
    assert resp.status_code == 202, resp.text

    session = SessionLocal()
    try:
        second_count = session.query(CodeAssignment).filter_by(run_id=run_id).count()
    finally:
        session.close()

    assert second_count == first_count
    assert first_count > 0
    assert first_count >= n_responses  # at least one assignment per response (catch-all fallback)

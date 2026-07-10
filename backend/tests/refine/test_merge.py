"""POST /api/runs/{id}/merge -- merged frequency must be the UNION of member
assignments, not the sum, and originals are removed from the child codebook."""

from app.db.base import SessionLocal
from app.models import CodeAssignment

TASTE_TEXTS = ["The taste is delicious and sweet.", "I love the flavor.", "Tastes amazing.", "Very tasty and delicious."]
PRICE_TEXTS = ["Great value for the price.", "It's affordable and cheap.", "Good price point.", "Worth the cost."]


def _code_ids(client, run_id):
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    return {c["name"]: c["code_id"] for c in codes}


def test_merge_originals_removed_and_merged_code_proposed(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    run_id = seeded["run_id"]
    ids = _code_ids(client, run_id)

    resp = client.post(f"/api/runs/{run_id}/merge", json={
        "code_ids": [ids["Taste & Flavor"], ids["Price & Value"]], "merged_name": "Taste & Price",
    })
    assert resp.status_code == 202, resp.text
    child_id = resp.json()["id"]
    assert client.get(f"/api/jobs/{resp.json()['job_id']}").json()["status"] == "finished"

    child_codes = client.get(f"/api/runs/{child_id}").json()["codebook"]["codes"]
    names = {c["name"] for c in child_codes}
    assert "Taste & Flavor" not in names
    assert "Price & Value" not in names
    merged = next(c for c in child_codes if c["name"] == "Taste & Price")
    assert merged["status"] == "proposed"
    assert set(merged.get("merged_from", [])) == {"Taste & Flavor", "Price & Value"}


def test_merge_frequency_is_union_not_sum(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    run_id = seeded["run_id"]
    org_id = seeded["user"]["org_id"]
    ids = _code_ids(client, run_id)
    taste_id, price_id = ids["Taste & Flavor"], ids["Price & Value"]

    # Force one response to genuinely carry BOTH codes -- the fake coder
    # never produces multi-label output on its own, so union-vs-sum can't be
    # distinguished without a real overlap to test against.
    taste_responses = client.get(f"/api/runs/{run_id}/responses", params={"code": taste_id, "page_size": 100}).json()["items"]
    overlap_response_id = taste_responses[0]["response_id"]

    session = SessionLocal()
    try:
        session.add(CodeAssignment(org_id=org_id, response_id=overlap_response_id, run_id=run_id, code_id=price_id, confidence=0.9))
        session.commit()
    finally:
        session.close()

    freq = {f["code"]: f["count"] for f in client.get(f"/api/runs/{run_id}/results/frequencies").json()["frequencies"]}
    taste_count, price_count = freq["Taste & Flavor"], freq["Price & Value"]
    assert taste_count == len(TASTE_TEXTS)
    assert price_count == len(PRICE_TEXTS) + 1  # +1 from the forced overlap

    merge_resp = client.post(f"/api/runs/{run_id}/merge", json={"code_ids": [taste_id, price_id], "merged_name": "Taste & Price"})
    child_id = merge_resp.json()["id"]
    merged = next(c for c in client.get(f"/api/runs/{child_id}").json()["codebook"]["codes"] if c["name"] == "Taste & Price")
    client.patch(f"/api/runs/{child_id}/codes/{merged['code_id']}", json={"status": "accepted"})
    assert client.post(f"/api/runs/{child_id}/finalize").status_code == 200
    assert client.post(f"/api/runs/{child_id}/apply").status_code == 202

    merged_freq = {f["code"]: f["count"] for f in client.get(f"/api/runs/{child_id}/results/frequencies").json()["frequencies"]}
    merged_count = merged_freq["Taste & Price"]

    # Union: |A ∪ B| = |A| + |B| - |A ∩ B| = taste_count + price_count - 1.
    assert merged_count == taste_count + price_count - 1
    # A naive sum (double-counting the overlap) would be strictly larger.
    assert merged_count < taste_count + price_count


def test_merge_requires_at_least_two_codes(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS, ["Taste & Flavor"])
    client = seeded["client"]
    resp = client.post(f"/api/runs/{seeded['run_id']}/merge", json={"code_ids": ["ONLYONE"]})
    assert resp.status_code == 422


def test_merge_unknown_code_id_returns_404(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    ids = _code_ids(client, seeded["run_id"])
    resp = client.post(f"/api/runs/{seeded['run_id']}/merge", json={"code_ids": [ids["Taste & Flavor"], "NOPE"]})
    assert resp.status_code == 404

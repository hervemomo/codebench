"""POST /api/questions/{id}/reset -- moves the active-run pointer along
lineage; nothing is deleted, and re-splitting from an earlier run branches
without disturbing whatever branch was previously active."""

TASTE_TEXTS = ["The taste is delicious and sweet.", "I love the flavor.", "Tastes amazing.", "Very tasty and delicious."]
PRICE_TEXTS = ["Great value for the price.", "It's affordable and cheap.", "Good price point.", "Worth the cost."]


def _taste_code_id(client, run_id):
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    return next(c["code_id"] for c in codes if c["name"] == "Taste & Flavor")


def _split_accept_finalize_apply(client, parent_run_id, names, defs):
    resp = client.post(f"/api/runs/{parent_run_id}/split", json={
        "parent_code_id": _taste_code_id(client, parent_run_id), "subcodes": names, "subcode_definitions": defs,
    })
    child_id = resp.json()["runs"][0]["id"]
    for c in client.get(f"/api/runs/{child_id}").json()["codebook"]["codes"]:
        if c["status"] == "proposed":
            client.patch(f"/api/runs/{child_id}/codes/{c['code_id']}", json={"status": "accepted"})
    assert client.post(f"/api/runs/{child_id}/finalize").status_code == 200
    assert client.post(f"/api/runs/{child_id}/apply").status_code == 202
    return child_id


def test_apply_auto_advances_active_run(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    # build_applied_run already applied s2 -- confirm the pointer landed there
    # by resetting to it explicitly and checking the response, since there's
    # no direct GET /questions/{id} endpoint to read active_run_id from.
    resp = seeded["client"].post(f"/api/questions/{seeded['question_id']}/reset", params={"to_run": seeded["run_id"]})
    assert resp.status_code == 200
    assert resp.json()["active_run_id"] == seeded["run_id"]


def test_reset_then_resplit_branches_without_disturbing_original_branch(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    s2_id = seeded["run_id"]

    child1_id = _split_accept_finalize_apply(client, s2_id, ["Sweetness", "Freshness"], ["d1", "d2"])

    reset_resp = client.post(f"/api/questions/{seeded['question_id']}/reset", params={"to_run": s2_id})
    assert reset_resp.status_code == 200
    assert reset_resp.json()["active_run_id"] == s2_id

    child2_id = _split_accept_finalize_apply(client, s2_id, ["Boldness", "Mildness"], ["d3", "d4"])
    assert child2_id != child1_id

    child1_after = client.get(f"/api/runs/{child1_id}").json()
    assert child1_after["status"] == "applied"
    assert child1_after["config"]["parent_run_id"] == s2_id
    child2_after = client.get(f"/api/runs/{child2_id}").json()
    assert child2_after["config"]["parent_run_id"] == s2_id

    final_reset = client.post(f"/api/questions/{seeded['question_id']}/reset", params={"to_run": child2_id})
    assert final_reset.json()["active_run_id"] == child2_id


def test_reset_rejects_run_from_a_different_question(build_applied_run):
    seeded_a = build_applied_run(TASTE_TEXTS, ["Taste & Flavor"])
    seeded_b = build_applied_run(PRICE_TEXTS, ["Price & Value"])

    resp = seeded_a["client"].post(f"/api/questions/{seeded_a['question_id']}/reset", params={"to_run": seeded_b["run_id"]})
    assert resp.status_code == 404


def test_reset_rejects_non_applied_run(build_applied_run, seed_dataset):
    seeded = build_applied_run(TASTE_TEXTS, ["Taste & Flavor"])
    client = seeded["client"]
    draft = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import", "codebook_source": ["Price & Value"],
    }).json()

    resp = client.post(f"/api/questions/{seeded['question_id']}/reset", params={"to_run": draft["id"]})
    assert resp.status_code == 409

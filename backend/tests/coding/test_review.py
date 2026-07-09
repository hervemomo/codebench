"""The DRAFT -> REVIEWED human review gate: accept/reject/edit codes, manual
add, and finalize()'s two guarantees -- no pending codes, catch-all present."""


def _create_import_run(seed_dataset, codebook_source):
    seeded = seed_dataset(["placeholder response " + str(i) for i in range(10)])
    client = seeded["client"]
    resp = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import", "codebook_source": codebook_source,
    })
    run_id = resp.json()["id"]
    return client, run_id


def test_patch_code_accept_reject_and_edit_persist(seed_dataset):
    client, run_id = _create_import_run(seed_dataset, ["Taste & Flavor", "Price & Value"])
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    taste_id = next(c["code_id"] for c in codes if c["name"] == "Taste & Flavor")
    price_id = next(c["code_id"] for c in codes if c["name"] == "Price & Value")

    resp = client.patch(f"/api/runs/{run_id}/codes/{taste_id}", json={"status": "accepted", "definition": "Edited definition."})
    assert resp.status_code == 200, resp.text
    resp = client.patch(f"/api/runs/{run_id}/codes/{price_id}", json={"status": "rejected"})
    assert resp.status_code == 200

    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    taste = next(c for c in codes if c["code_id"] == taste_id)
    price = next(c for c in codes if c["code_id"] == price_id)
    assert taste["status"] == "accepted"
    assert taste["definition"] == "Edited definition."
    assert price["status"] == "rejected"


def test_patch_unknown_code_id_returns_404(seed_dataset):
    client, run_id = _create_import_run(seed_dataset, ["Taste & Flavor"])
    resp = client.patch(f"/api/runs/{run_id}/codes/NOPE", json={"status": "accepted"})
    assert resp.status_code == 404


def test_manual_add_code_is_accepted_immediately(seed_dataset):
    client, run_id = _create_import_run(seed_dataset, ["Taste & Flavor"])
    resp = client.post(f"/api/runs/{run_id}/codes", json={"name": "Manual Code", "definition": "Hand-typed."})
    assert resp.status_code == 201, resp.text
    codes = resp.json()["codebook"]["codes"]
    manual = next(c for c in codes if c["name"] == "Manual Code")
    assert manual["status"] == "accepted"
    assert manual["source"] == "manual"
    assert manual["code_id"]


def test_finalize_rejects_run_with_codes_still_proposed(seed_dataset):
    client, run_id = _create_import_run(seed_dataset, ["Taste & Flavor", "Price & Value"])
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    taste_id = next(c["code_id"] for c in codes if c["name"] == "Taste & Flavor")
    client.patch(f"/api/runs/{run_id}/codes/{taste_id}", json={"status": "accepted"})
    # Price & Value is still "proposed" -- finalize must 409.

    resp = client.post(f"/api/runs/{run_id}/finalize")
    assert resp.status_code == 409


def test_finalize_injects_catch_all_when_missing_and_flips_to_reviewed(seed_dataset):
    client, run_id = _create_import_run(seed_dataset, ["Taste & Flavor"])
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    for c in codes:
        client.patch(f"/api/runs/{run_id}/codes/{c['code_id']}", json={"status": "accepted"})

    resp = client.post(f"/api/runs/{run_id}/finalize")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "reviewed"
    accepted = [c for c in body["codebook"]["codes"] if c["status"] == "accepted"]
    assert any(c.get("source") == "system_catch_all" for c in accepted)


def test_finalize_does_not_duplicate_catch_all_if_already_accepted(seed_dataset):
    client, run_id = _create_import_run(seed_dataset, ["Other / Not classifiable"])
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    client.patch(f"/api/runs/{run_id}/codes/{codes[0]['code_id']}", json={"status": "accepted"})

    resp = client.post(f"/api/runs/{run_id}/finalize")
    assert resp.status_code == 200
    accepted = [c for c in resp.json()["codebook"]["codes"] if c["status"] == "accepted"]
    assert len(accepted) == 1


def test_apply_blocked_unless_reviewed(seed_dataset):
    client, run_id = _create_import_run(seed_dataset, ["Taste & Flavor"])
    resp = client.post(f"/api/runs/{run_id}/apply")
    assert resp.status_code == 409


def test_codes_cannot_be_edited_once_finalized(seed_dataset):
    client, run_id = _create_import_run(seed_dataset, ["Taste & Flavor"])
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    code_id = codes[0]["code_id"]
    client.patch(f"/api/runs/{run_id}/codes/{code_id}", json={"status": "accepted"})
    client.post(f"/api/runs/{run_id}/finalize")

    resp = client.patch(f"/api/runs/{run_id}/codes/{code_id}", json={"status": "rejected"})
    assert resp.status_code == 409

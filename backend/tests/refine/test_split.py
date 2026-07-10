"""POST /api/runs/{id}/split -- reuses Sequence 4's review/finalize/apply
gate on the resulting child run; only creation differs."""

TASTE_TEXTS = [
    "The taste is delicious and sweet.", "I love the flavor.", "Tastes amazing.",
    "Very tasty and delicious.", "Great flavor, love it.", "Delicious taste every time.",
]
PRICE_TEXTS = [
    "Great value for the price.", "It's affordable and cheap.", "Good price point.", "Worth the cost.",
]


def _taste_code_id(client, run_id):
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    return next(c["code_id"] for c in codes if c["name"] == "Taste & Flavor")


def test_split_creates_draft_child_with_correct_lineage(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    run_id = seeded["run_id"]
    taste_id = _taste_code_id(client, run_id)

    resp = client.post(f"/api/runs/{run_id}/split", json={
        "parent_code_id": taste_id, "subcodes": ["Sweetness", "Freshness"],
        "subcode_definitions": ["Mentions sweetness.", "Mentions freshness."],
    })
    assert resp.status_code == 202, resp.text
    child_id = resp.json()["runs"][0]["id"]
    job_id = resp.json()["runs"][0]["job_id"]
    assert client.get(f"/api/jobs/{job_id}").json()["status"] == "finished"

    child = client.get(f"/api/runs/{child_id}").json()
    assert child["status"] == "draft"
    assert child["kind"] == "split"
    assert child["config"]["parent_run_id"] == run_id
    assert child["question_id"] == seeded["question_id"]


def test_split_redistributes_parent_rows_and_removes_parent_by_default(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    run_id = seeded["run_id"]
    taste_id = _taste_code_id(client, run_id)

    resp = client.post(f"/api/runs/{run_id}/split", json={
        "parent_code_id": taste_id, "subcodes": ["Sweetness", "Freshness"],
        "subcode_definitions": ["Mentions sweetness.", "Mentions freshness."],
    })
    child_id = resp.json()["runs"][0]["id"]

    child_codes = client.get(f"/api/runs/{child_id}").json()["codebook"]["codes"]
    names = {c["name"] for c in child_codes}
    assert "Taste & Flavor" not in names
    assert {"Sweetness", "Freshness"} <= names
    price = next(c for c in child_codes if c["name"] == "Price & Value")
    assert price["status"] == "accepted"  # inherited, unaffected -- no re-review needed
    sweetness = next(c for c in child_codes if c["name"] == "Sweetness")
    assert sweetness["status"] == "proposed"

    for c in child_codes:
        if c["status"] == "proposed":
            client.patch(f"/api/runs/{child_id}/codes/{c['code_id']}", json={"status": "accepted"})
    assert client.post(f"/api/runs/{child_id}/finalize").status_code == 200
    assert client.post(f"/api/runs/{child_id}/apply").status_code == 202

    qa = client.get(f"/api/runs/{child_id}/qa").json()
    assert qa["total_valid"] == len(TASTE_TEXTS) + len(PRICE_TEXTS)
    assert qa["uncoded_count"] == 0  # every parent row landed on a sub-code, Price&Value, or Other

    freq = {f["code"]: f["count"] for f in client.get(f"/api/runs/{child_id}/results/frequencies").json()["frequencies"]}
    assert "Taste & Flavor" not in freq
    assert freq.get("Sweetness", 0) + freq.get("Freshness", 0) == len(TASTE_TEXTS)


def test_split_preserves_parent_when_requested(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    run_id = seeded["run_id"]
    taste_id = _taste_code_id(client, run_id)

    resp = client.post(f"/api/runs/{run_id}/split", json={
        "parent_code_id": taste_id, "subcodes": ["Sweetness", "Freshness"],
        "subcode_definitions": ["d1", "d2"], "preserve_parent": True,
    })
    child_id = resp.json()["runs"][0]["id"]
    names = {c["name"] for c in client.get(f"/api/runs/{child_id}").json()["codebook"]["codes"]}
    assert "Taste & Flavor" in names
    assert {"Sweetness", "Freshness"} <= names


def test_split_multi_config_creates_one_child_run_each(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    run_id = seeded["run_id"]
    taste_id = _taste_code_id(client, run_id)

    resp = client.post(f"/api/runs/{run_id}/split", json={
        "parent_code_id": taste_id,
        "configs": [
            {"subcodes": ["Sweetness", "Freshness"], "subcode_definitions": ["d1", "d2"]},
            {"subcodes": ["Boldness", "Mildness"], "subcode_definitions": ["d3", "d4"]},
        ],
    })
    assert resp.status_code == 202, resp.text
    runs = resp.json()["runs"]
    assert len(runs) == 2
    assert runs[0]["id"] != runs[1]["id"]
    names_a = {c["name"] for c in client.get(f"/api/runs/{runs[0]['id']}").json()["codebook"]["codes"]}
    names_b = {c["name"] for c in client.get(f"/api/runs/{runs[1]['id']}").json()["codebook"]["codes"]}
    assert {"Sweetness", "Freshness"} <= names_a
    assert {"Boldness", "Mildness"} <= names_b


def test_split_requires_applied_parent(build_applied_run, seed_dataset):
    seeded = seed_dataset(TASTE_TEXTS)
    client = seeded["client"]
    draft_run_id = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import", "codebook_source": ["Taste & Flavor"],
    }).json()["id"]

    resp = client.post(f"/api/runs/{draft_run_id}/split", json={"parent_code_id": "X", "subcodes": ["A", "B"]})
    assert resp.status_code == 409


def test_split_unknown_parent_code_id_returns_404(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS, ["Taste & Flavor"])
    resp = seeded["client"].post(f"/api/runs/{seeded['run_id']}/split", json={"parent_code_id": "NOPE", "subcodes": ["A", "B"]})
    assert resp.status_code == 404

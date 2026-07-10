"""GET /api/runs/{id}/responses -- pagination/search/filter math on a
200-row fixture, plus the results/frequencies|cooccurrence|codebook reads."""

TASTE_TEXTS = [f"The taste is delicious, variant {i}." for i in range(100)]
PRICE_TEXTS = [f"Great value for the price, variant {i}." for i in range(100)]


def test_pagination_math_on_200_row_fixture(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    run_id = seeded["run_id"]

    page1 = client.get(f"/api/runs/{run_id}/responses", params={"page": 1, "page_size": 50}).json()
    assert page1["total"] == 200
    assert len(page1["items"]) == 50

    page4 = client.get(f"/api/runs/{run_id}/responses", params={"page": 4, "page_size": 50}).json()
    assert len(page4["items"]) == 50

    page5_out_of_range = client.get(f"/api/runs/{run_id}/responses", params={"page": 5, "page_size": 50}).json()
    assert len(page5_out_of_range["items"]) == 0
    assert page5_out_of_range["total"] == 200

    all_ids = set()
    for page in range(1, 5):
        items = client.get(f"/api/runs/{run_id}/responses", params={"page": page, "page_size": 50}).json()["items"]
        all_ids.update(item["response_id"] for item in items)
    assert len(all_ids) == 200  # every response appears exactly once across pages


def test_search_filters_by_text_substring(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    run_id = seeded["run_id"]

    result = client.get(f"/api/runs/{run_id}/responses", params={"search": "price", "page_size": 200}).json()
    assert result["total"] == 100
    assert all("price" in item["text"].lower() for item in result["items"])


def test_code_filter_matches_frequency_count(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS + PRICE_TEXTS, ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    run_id = seeded["run_id"]

    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    taste_id = next(c["code_id"] for c in codes if c["name"] == "Taste & Flavor")

    filtered = client.get(f"/api/runs/{run_id}/responses", params={"code": taste_id, "page_size": 200}).json()
    freq = {f["code"]: f["count"] for f in client.get(f"/api/runs/{run_id}/results/frequencies").json()["frequencies"]}
    assert filtered["total"] == freq["Taste & Flavor"]
    assert all("Taste & Flavor" in item["codes"] for item in filtered["items"])


def test_results_codebook_returns_only_accepted_codes(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS[:5] + PRICE_TEXTS[:5], ["Taste & Flavor", "Price & Value"])
    client = seeded["client"]
    codes = client.get(f"/api/runs/{seeded['run_id']}/results/codebook").json()["codes"]
    assert all(c["status"] == "accepted" for c in codes)
    names = {c["name"] for c in codes}
    assert {"Taste & Flavor", "Price & Value"} <= names


def test_results_cooccurrence_shape(build_applied_run):
    seeded = build_applied_run(TASTE_TEXTS[:5] + PRICE_TEXTS[:5], ["Taste & Flavor", "Price & Value"])
    cooc = seeded["client"].get(f"/api/runs/{seeded['run_id']}/results/cooccurrence").json()
    n = len(cooc["codes"])
    assert n > 0
    assert len(cooc["matrix"]) == n
    assert all(len(row) == n for row in cooc["matrix"])


def test_results_require_applied_run(seed_dataset):
    seeded = seed_dataset(TASTE_TEXTS[:5])
    client = seeded["client"]
    draft_run_id = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import", "codebook_source": ["Taste & Flavor"],
    }).json()["id"]

    assert client.get(f"/api/runs/{draft_run_id}/results/frequencies").status_code == 409
    assert client.get(f"/api/runs/{draft_run_id}/responses").status_code == 409

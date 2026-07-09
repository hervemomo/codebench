"""QA metrics: a pure-function test against a hand-built fixture (known
catch-all rate, low-confidence samples, near-zero codes, co-occurring pairs),
plus a lighter end-to-end check that the API wires real DB rows into it."""

from app.qa import compute_qa_metrics
from tests.fixtures.fake_openai import NO_MATCH_MARKER

CODES = [
    {"code_id": "TASTE", "name": "Taste & Flavor", "is_catch_all": False},
    {"code_id": "PACKAGING", "name": "Packaging & Design", "is_catch_all": False},
    {"code_id": "OTHER", "name": "Other / Not classifiable", "is_catch_all": True},
]


def test_compute_qa_metrics_on_hand_built_fixture():
    # 25 valid responses: 23 get exactly one non-other code, 2 land in Other
    # (simulating the LLM's no-match fallback), and one response gets both
    # Taste and Packaging to exercise the co-occurrence count. Packaging never
    # appears alone, so it's a near-zero-frequency code (1/25 = 4% is fine,
    # but 0 solo assignments is what we assert on a *different* code below).
    valid_ids = list(range(1, 26))
    assignments = []
    for rid in range(1, 21):  # 20 responses -> Taste only
        assignments.append({"response_id": rid, "code_id": "TASTE", "code_name": "Taste & Flavor", "confidence": 0.9, "text": "t"})
    for rid in range(21, 23):  # 2 responses -> Taste + Packaging (co-occurrence)
        assignments.append({"response_id": rid, "code_id": "TASTE", "code_name": "Taste & Flavor", "confidence": 0.9, "text": "t"})
        assignments.append({"response_id": rid, "code_id": "PACKAGING", "code_name": "Packaging & Design", "confidence": 0.85, "text": "t"})
    for rid in range(23, 25):  # 2 responses -> catch-all (known rate: 2/25)
        assignments.append({"response_id": rid, "code_id": "OTHER", "code_name": "Other / Not classifiable", "confidence": 0.50, "text": "no match"})
    # response 25 intentionally has zero assignments (uncoded)

    metrics = compute_qa_metrics(valid_response_ids=valid_ids, assignments=assignments, codes=CODES)

    assert metrics["total_valid"] == 25
    assert metrics["catch_all_count"] == 2
    assert metrics["catch_all_rate"] == 2 / 25
    assert metrics["uncoded_count"] == 1
    assert metrics["uncoded_rate"] == 1 / 25

    assert len(metrics["low_confidence_samples"]) == 2
    assert all(s["code_id"] == "OTHER" for s in metrics["low_confidence_samples"])

    # pair_counts keys sort code_ids alphabetically: "PACKAGING" < "TASTE".
    assert metrics["top_cooccurring_pairs"] == [{"code_a": "Packaging & Design", "code_b": "Taste & Flavor", "count": 2}]

    # Packaging appears twice (2/25 = 8%), above the 2% near-zero threshold,
    # so only a genuinely near-zero code should show up here.
    near_zero_names = {c["name"] for c in metrics["near_zero_frequency_codes"]}
    assert "Packaging & Design" not in near_zero_names


def test_compute_qa_metrics_near_zero_threshold():
    codes = [
        {"code_id": "A", "name": "Common", "is_catch_all": False},
        {"code_id": "B", "name": "Rare", "is_catch_all": False},
        {"code_id": "OTHER", "name": "Other", "is_catch_all": True},
    ]
    valid_ids = list(range(1, 101))
    assignments = [{"response_id": i, "code_id": "A", "code_name": "Common", "confidence": 0.9, "text": ""} for i in range(1, 96)]
    assignments += [{"response_id": i, "code_id": "B", "code_name": "Rare", "confidence": 0.9, "text": ""} for i in range(96, 97)]

    metrics = compute_qa_metrics(valid_response_ids=valid_ids, assignments=assignments, codes=codes)

    near_zero = {c["name"]: c["count"] for c in metrics["near_zero_frequency_codes"]}
    assert near_zero == {"Rare": 1}


def test_qa_endpoint_requires_applied_run(seed_dataset):
    seeded = seed_dataset(["placeholder " + str(i) for i in range(10)])
    client = seeded["client"]
    run_id = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import", "codebook_source": ["Taste & Flavor"],
    }).json()["id"]

    resp = client.get(f"/api/runs/{run_id}/qa")
    assert resp.status_code == 409


def test_qa_endpoint_reflects_real_applied_run(seed_dataset):
    texts = ["The taste is delicious." for _ in range(8)] + [f"{NO_MATCH_MARKER} nothing to say" for _ in range(2)]
    seeded = seed_dataset(texts)
    client = seeded["client"]

    run_id = client.post(f"/api/questions/{seeded['question_id']}/runs", json={
        "kind": "import", "codebook_source": ["Taste & Flavor"],
    }).json()["id"]
    codes = client.get(f"/api/runs/{run_id}").json()["codebook"]["codes"]
    client.patch(f"/api/runs/{run_id}/codes/{codes[0]['code_id']}", json={"status": "accepted"})
    client.post(f"/api/runs/{run_id}/finalize")
    client.post(f"/api/runs/{run_id}/apply")

    qa = client.get(f"/api/runs/{run_id}/qa").json()
    assert qa["total_valid"] == 10
    assert qa["catch_all_count"] == 2
    assert qa["catch_all_rate"] == 2 / 10
    assert qa["uncoded_count"] == 0

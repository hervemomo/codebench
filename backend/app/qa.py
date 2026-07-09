"""Pure QA-metric computations for the post-apply review gate (QA Review page).

Operates on plain dicts, not the ORM, so it's directly unit-testable against
a hand-built fixture -- see tests/coding/test_qa.py. app/routers/coding.py
loads the DB rows and hands them to compute_qa_metrics().
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations

DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.65
DEFAULT_NEAR_ZERO_THRESHOLD = 0.02
DEFAULT_LOW_CONFIDENCE_LIMIT = 20
DEFAULT_TOP_PAIRS_LIMIT = 5


def compute_qa_metrics(
    *,
    valid_response_ids: list[int],
    assignments: list[dict],
    codes: list[dict],
    low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    near_zero_threshold: float = DEFAULT_NEAR_ZERO_THRESHOLD,
    low_confidence_limit: int = DEFAULT_LOW_CONFIDENCE_LIMIT,
    top_pairs_limit: int = DEFAULT_TOP_PAIRS_LIMIT,
) -> dict:
    """`assignments`: [{response_id, code_id, code_name, confidence, text}].
    `codes`: [{code_id, name, is_catch_all}] -- the accepted codebook."""
    total_valid = len(valid_response_ids)

    by_response: dict[int, list[dict]] = {}
    for a in assignments:
        by_response.setdefault(a["response_id"], []).append(a)

    uncoded_ids = [rid for rid in valid_response_ids if rid not in by_response]
    uncoded_rate = (len(uncoded_ids) / total_valid) if total_valid else 0.0

    catch_all_code_ids = {c["code_id"] for c in codes if c.get("is_catch_all")}
    catch_all_response_ids = {a["response_id"] for a in assignments if a["code_id"] in catch_all_code_ids}
    catch_all_rate = (len(catch_all_response_ids) / total_valid) if total_valid else 0.0

    histogram: Counter = Counter()
    for rid in valid_response_ids:
        histogram[str(len(by_response.get(rid, [])))] += 1

    low_confidence_samples = sorted(
        (a for a in assignments if a["confidence"] < low_confidence_threshold),
        key=lambda a: a["confidence"],
    )[:low_confidence_limit]

    code_counts = Counter(a["code_id"] for a in assignments)
    near_zero_frequency_codes = [
        {
            "code_id": c["code_id"],
            "name": c["name"],
            "count": code_counts.get(c["code_id"], 0),
            "rate": (code_counts.get(c["code_id"], 0) / total_valid) if total_valid else 0.0,
        }
        for c in codes
        if not c.get("is_catch_all")
        and ((code_counts.get(c["code_id"], 0) / total_valid) if total_valid else 0.0) < near_zero_threshold
    ]

    pair_counts: Counter = Counter()
    for items in by_response.values():
        ids = sorted({a["code_id"] for a in items})
        for a, b in combinations(ids, 2):
            pair_counts[(a, b)] += 1
    name_by_id = {c["code_id"]: c["name"] for c in codes}
    top_cooccurring_pairs = [
        {"code_a": name_by_id.get(a, a), "code_b": name_by_id.get(b, b), "count": n}
        for (a, b), n in pair_counts.most_common(top_pairs_limit)
    ]

    n_coded = len(by_response)
    avg_codes_per_response = (len(assignments) / n_coded) if n_coded else 0.0

    return {
        "total_valid": total_valid,
        "total_coded": n_coded,
        "uncoded_count": len(uncoded_ids),
        "uncoded_rate": uncoded_rate,
        "catch_all_count": len(catch_all_response_ids),
        "catch_all_rate": catch_all_rate,
        "avg_codes_per_response": avg_codes_per_response,
        "multi_label_histogram": dict(histogram),
        "low_confidence_samples": low_confidence_samples,
        "near_zero_frequency_codes": near_zero_frequency_codes,
        "top_cooccurring_pairs": top_cooccurring_pairs,
    }

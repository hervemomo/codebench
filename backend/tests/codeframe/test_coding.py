import math

import pandas as pd

from codeframe.codebook import Codebook, generate_codebook, get_default_other_code_name
from codeframe.coding import add_codes_column, apply_codes
from codeframe.config import CodingConfig


def _codebook_for(fake_client, project_cfg, coding_cfg, sample_texts):
    representatives = {i: sample_texts[i * 6 : i * 6 + 3] for i in range(5)}
    return generate_codebook(fake_client, representatives, project_cfg, coding_cfg, target_codes=5)


def test_apply_codes_every_kept_row_gets_at_least_one_code(fake_client, project_cfg, coding_cfg, sample_texts):
    codebook = _codebook_for(fake_client, project_cfg, coding_cfg, sample_texts)
    df = pd.DataFrame({project_cfg.text_column: sample_texts})

    coded = apply_codes(df, codebook, project_cfg, coding_cfg, fake_client)

    code_cols = [f"code_{c.name}" for c in codebook.codes]
    assert (coded[code_cols].sum(axis=1) >= 1).all()


def test_apply_codes_batching_math_and_progress_callback(fake_client, project_cfg, sample_texts):
    coding_cfg = CodingConfig(coding_batch_size=7)
    codebook = _codebook_for(fake_client, project_cfg, coding_cfg, sample_texts)
    df = pd.DataFrame({project_cfg.text_column: sample_texts})  # 30 unique texts

    calls = []
    apply_codes(df, codebook, project_cfg, coding_cfg, fake_client, progress_cb=lambda i, n: calls.append((i, n)))

    expected_batches = math.ceil(len(sample_texts) / coding_cfg.coding_batch_size)
    assert len(calls) == expected_batches
    assert calls[-1] == (expected_batches, expected_batches)
    assert [c[0] for c in calls] == list(range(1, expected_batches + 1))


def test_apply_codes_uncoded_rows_fall_back_to_other(fake_client, project_cfg, coding_cfg):
    other_name = get_default_other_code_name(project_cfg)
    codebook = Codebook.from_dict({"codes": [
        {"name": "Specific Theme", "definition": "very specific"},
        {"name": other_name, "definition": "catch-all"},
    ]})
    df = pd.DataFrame({project_cfg.text_column: ["###NO_MATCH### this text matches nothing"]})

    coded = apply_codes(df, codebook, project_cfg, coding_cfg, fake_client)

    assert coded.iloc[0][f"code_{other_name}"] == 1


def test_apply_codes_reasoning_saved_only_when_configured(fake_client, project_cfg, sample_texts):
    representatives = {0: sample_texts[0:3]}
    no_reason_cfg = CodingConfig(save_coding_reasoning=False)
    codebook = generate_codebook(fake_client, representatives, project_cfg, no_reason_cfg, target_codes=1)
    df = pd.DataFrame({project_cfg.text_column: sample_texts[0:6]})

    coded_without = apply_codes(df, codebook, project_cfg, no_reason_cfg, fake_client)
    assert all('"reasoning"' not in r for r in coded_without["coding_result"])

    reason_cfg = CodingConfig(save_coding_reasoning=True)
    coded_with = apply_codes(df, codebook, project_cfg, reason_cfg, fake_client)
    assert any('"reasoning"' in r for r in coded_with["coding_result"])


def test_apply_codes_falls_back_to_single_item_coding_when_batch_unparseable(fake_client, project_cfg, coding_cfg):
    codebook = Codebook.from_dict({"codes": [
        {"name": "Taste & Flavor", "definition": "taste"},
        {"name": get_default_other_code_name(project_cfg), "definition": "catch-all"},
    ]})
    df = pd.DataFrame({project_cfg.text_column: ["great taste today BATCH_CODE_FAIL", "another response BATCH_CODE_FAIL"]})

    coded = apply_codes(df, codebook, project_cfg, coding_cfg, fake_client)

    # Both rows still get coded via the per-item fallback path.
    code_cols = [f"code_{c.name}" for c in codebook.codes]
    assert (coded[code_cols].sum(axis=1) >= 1).all()


def test_apply_codes_hallucinated_code_name_falls_back_to_other(fake_client, project_cfg, coding_cfg):
    other_name = get_default_other_code_name(project_cfg)
    codebook = Codebook.from_dict({"codes": [
        {"name": "Taste & Flavor", "definition": "taste"},
        {"name": other_name, "definition": "catch-all"},
    ]})
    df = pd.DataFrame({project_cfg.text_column: ["###INVALID_CODE### this response gets a hallucinated code"]})

    coded = apply_codes(df, codebook, project_cfg, coding_cfg, fake_client)

    result = coded.iloc[0]["coding_result"]
    assert coded.iloc[0][f"code_{other_name}"] == 1
    assert "invalid_returned_codes" in result


def test_apply_codes_logs_uncoded_rows_when_no_catchall_exists(fake_client, project_cfg, coding_cfg):
    codebook = Codebook.from_dict({"codes": [{"name": "Only Specific Theme", "definition": "specific"}]})
    df = pd.DataFrame({project_cfg.text_column: ["###NO_MATCH### nothing matches and there is no catch-all"]})

    coded = apply_codes(df, codebook, project_cfg, coding_cfg, fake_client)

    assert coded["code_Only Specific Theme"].iloc[0] == 0


def test_add_codes_column_is_idempotent_when_called_twice(project_cfg):
    codebook = Codebook.from_dict({"codes": [{"name": "Code A"}]})
    df = pd.DataFrame({project_cfg.text_column: ["r1", "r2"], "code_Code A": [1, 0]})

    once = add_codes_column(df, codebook)
    twice = add_codes_column(once, codebook)

    assert twice["codes"].tolist() == once["codes"].tolist()

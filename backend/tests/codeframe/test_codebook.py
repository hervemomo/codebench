import json

import pandas as pd
import pytest

from codeframe.codebook import (
    Code,
    Codebook,
    enrich_with_ai,
    ensure_other_code,
    generate_codebook,
    get_default_other_code_name,
    get_other_code_name,
    load_user_codebook,
    to_compact_prompt,
    to_full_prompt,
)
from codeframe.config import CodingConfig


def _other_name(project_cfg):
    return get_default_other_code_name(project_cfg)


def test_generate_codebook_parses_fake_json_and_adds_catchall(fake_client, project_cfg, coding_cfg, sample_texts):
    representatives = {0: sample_texts[0:3], 1: sample_texts[6:9]}

    cb = generate_codebook(fake_client, representatives, project_cfg, coding_cfg, target_codes=2)

    assert len(cb.codes) == 3  # 2 themes + catch-all
    assert get_other_code_name(cb, _other_name(project_cfg)) is not None
    assert cb.model == project_cfg.reasoning_model


def test_generate_codebook_respects_target_codes_cap(fake_client, project_cfg, coding_cfg, sample_texts):
    representatives = {i: sample_texts[i * 6 : i * 6 + 3] for i in range(5)}
    target = 3

    cb = generate_codebook(fake_client, representatives, project_cfg, coding_cfg, target_codes=target)

    non_other = [c for c in cb.codes if c.name != _other_name(project_cfg)]
    assert len(non_other) == target


def test_generate_codebook_truncation_retry_path(fake_client, project_cfg):
    tiny_budget_cfg = CodingConfig(codebook_generation_max_tokens=10, codebook_generation_retry_max_tokens=8000)
    representatives = {0: ["alpha text sample"], 1: ["beta text sample"], 2: ["gamma text sample"]}

    cb = generate_codebook(fake_client, representatives, project_cfg, tiny_budget_cfg, target_codes=3)

    non_other = [c for c in cb.codes if c.name != _other_name(project_cfg)]
    assert len(non_other) == 3


def test_generate_codebook_raises_when_both_budgets_too_small(fake_client, project_cfg):
    tiny_budget_cfg = CodingConfig(codebook_generation_max_tokens=1, codebook_generation_retry_max_tokens=1)
    representatives = {0: ["alpha"], 1: ["beta"], 2: ["gamma"]}

    with pytest.raises(ValueError):
        generate_codebook(fake_client, representatives, project_cfg, tiny_budget_cfg, target_codes=3)


def test_load_user_codebook_from_list():
    cb = load_user_codebook(["Code A", "Code B", {"name": "Code C", "definition": "def c"}])
    assert [c.name for c in cb.codes] == ["Code A", "Code B", "Code C"]
    assert cb.get_code("Code C").definition == "def c"


def test_load_user_codebook_from_xlsx(tmp_path):
    df = pd.DataFrame({"Code Name": ["Code A", "Code B"], "Code ID": ["A1", "B1"], "Definition": ["d1", "d2"]})
    path = tmp_path / "cb.xlsx"
    df.to_excel(path, index=False)

    cb = load_user_codebook(path, name_column="Code Name", id_column="Code ID", definition_column="Definition")

    assert cb.has_code_ids()
    assert cb.codes[0].code_id == "A1"
    assert cb.codes[0].definition == "d1"


def test_load_user_codebook_from_csv(tmp_path):
    path = tmp_path / "cb.csv"
    pd.DataFrame({"Code Name": ["Code A", "Code B"]}).to_csv(path, index=False)

    cb = load_user_codebook(path, name_column="Code Name")

    assert len(cb.codes) == 2


def test_load_user_codebook_from_json(tmp_path):
    path = tmp_path / "cb.json"
    path.write_text(json.dumps([{"name": "Code A"}, {"name": "Code B", "definition": "d"}]), encoding="utf-8")

    cb = load_user_codebook(path)

    assert len(cb.codes) == 2
    assert cb.get_code("Code B").definition == "d"


def test_load_user_codebook_rejects_duplicate_names():
    with pytest.raises(ValueError):
        load_user_codebook(["Code A", "Code A"])


def test_ensure_other_code_always_present_and_idempotent(project_cfg):
    cb = load_user_codebook(["Code A", "Code B"])

    cb = ensure_other_code(project_cfg, cb)
    assert get_other_code_name(cb, _other_name(project_cfg)) is not None
    n_after_first = len(cb.codes)

    cb = ensure_other_code(project_cfg, cb)
    assert len(cb.codes) == n_after_first


def test_to_compact_prompt_and_full_prompt_render_all_codes():
    cb = Codebook.from_dict({"codes": [
        {"name": "Code A", "definition": "def a"},
        {"name": "Code B", "definition": "def b"},
    ]})

    compact = to_compact_prompt(cb)
    full = to_full_prompt(cb)

    assert "Code A" in compact and "Code B" in compact
    assert "Code A" in full and "Code B" in full
    assert "def a" in full


def test_enrich_with_ai_skips_when_all_codes_already_defined(fake_client, project_cfg, coding_cfg):
    cb = Codebook(codes=[Code(name="Code A", definition="already defined")])

    result = enrich_with_ai(fake_client, cb, project_cfg, coding_cfg)

    assert result is cb
    assert result.codes[0].definition == "already defined"


def test_enrich_with_ai_preserves_predefined_and_fills_missing(fake_client, project_cfg, coding_cfg):
    cb = Codebook(codes=[Code(name="Predefined", definition="keep me"), Code(name="Needs Def")])

    result = enrich_with_ai(fake_client, cb, project_cfg, coding_cfg)

    assert result.get_code("Predefined").definition == "keep me"
    assert result.get_code("Needs Def").definition


def test_enrich_with_ai_falls_back_deterministically_when_llm_call_fails(project_cfg, coding_cfg):
    class _BrokenCompletions:
        def create(self, **kwargs):
            raise RuntimeError("simulated LLM outage")

    class _BrokenClient:
        def __init__(self):
            self.chat = type("_Chat", (), {"completions": _BrokenCompletions()})()

    cb = Codebook(codes=[Code(name="Needs Def")])

    result = enrich_with_ai(_BrokenClient(), cb, project_cfg, coding_cfg, fill_missing_with_fallback=True)

    assert result.codes[0].definition
    assert result.codes[0].definition_source == "deterministic_fallback"

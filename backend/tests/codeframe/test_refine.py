import copy

import pandas as pd
import pytest

from codeframe.codebook import Codebook, get_default_other_code_name
from codeframe.refine import merge_codes, split_code


def _base_codebook_and_df(project_cfg):
    other_name = get_default_other_code_name(project_cfg)
    codebook = Codebook.from_dict({"codes": [
        {"name": "Broad Theme", "definition": "broad"},
        {"name": other_name, "definition": "catch-all"},
    ]})
    texts = [f"response about broad theme number {i}" for i in range(4)] + ["totally unrelated response text"]
    df = pd.DataFrame({project_cfg.text_column: texts})
    df["code_Broad Theme"] = [1, 1, 1, 1, 0]
    df["conf_Broad Theme"] = [0.9, 0.9, 0.9, 0.9, 0.0]
    df[f"code_{other_name}"] = [0, 0, 0, 0, 1]
    df[f"conf_{other_name}"] = [0.0, 0.0, 0.0, 0.0, 0.5]
    return codebook, df


def test_split_code_reassigns_parent_rows_and_removes_parent(fake_client, project_cfg, coding_cfg):
    codebook, df = _base_codebook_and_df(project_cfg)
    original_df = df.copy(deep=True)
    original_codebook = copy.deepcopy(codebook)

    new_df, new_codebook = split_code(
        df, codebook, fake_client, "Broad Theme", project_cfg, coding_cfg,
        n_subcodes_proposed=2, enrich_subcodes=True,
    )

    # Inputs are never mutated.
    pd.testing.assert_frame_equal(df, original_df)
    assert [c.name for c in codebook.codes] == [c.name for c in original_codebook.codes]

    # Parent removed, replaced by exactly 2 subcodes.
    assert "code_Broad Theme" not in new_df.columns
    subcode_names = [c.name for c in new_codebook.codes if c.parent_code == "Broad Theme"]
    assert len(subcode_names) == 2

    # The 4 previously-parent-coded rows are redistributed, one subcode each.
    subcode_cols = [f"code_{n}" for n in subcode_names]
    assert (new_df.loc[0:3, subcode_cols].sum(axis=1) == 1).all()


def test_split_code_preserves_parent_when_configured(fake_client, project_cfg, coding_cfg):
    codebook, df = _base_codebook_and_df(project_cfg)

    new_df, new_codebook = split_code(
        df, codebook, fake_client, "Broad Theme", project_cfg, coding_cfg,
        n_subcodes_proposed=2, enrich_subcodes=True, preserve_parent=True,
    )

    assert "code_Broad Theme" in new_df.columns
    assert new_codebook.get_code("Broad Theme") is not None


def test_split_code_manual_subcodes_are_respected(fake_client, project_cfg, coding_cfg):
    codebook, df = _base_codebook_and_df(project_cfg)

    _, new_codebook = split_code(
        df, codebook, fake_client, "Broad Theme", project_cfg, coding_cfg,
        subcodes=["Sub One", "Sub Two"], subcode_definitions=["def one", "def two"], enrich_subcodes=False,
    )

    names = {c.name for c in new_codebook.codes}
    assert {"Sub One", "Sub Two"}.issubset(names)


def test_merge_codes_unions_assignments_and_removes_originals(fake_client, project_cfg, coding_cfg):
    codebook = Codebook.from_dict({"codes": [
        {"name": "Code A", "definition": "a"},
        {"name": "Code B", "definition": "b"},
    ]})
    df = pd.DataFrame({project_cfg.text_column: ["r1", "r2", "r3", "r4"]})
    df["code_Code A"] = [1, 1, 0, 0]
    df["conf_Code A"] = [0.8, 0.6, 0.0, 0.0]
    df["code_Code B"] = [0, 1, 1, 0]
    df["conf_Code B"] = [0.0, 0.7, 0.5, 0.0]
    original_df = df.copy(deep=True)
    original_codebook = copy.deepcopy(codebook)

    new_df, new_codebook = merge_codes(
        df, codebook, fake_client, ["Code A", "Code B"], project_cfg, coding_cfg, merged_name="Combined Code",
    )

    # Inputs are never mutated.
    pd.testing.assert_frame_equal(df, original_df)
    assert [c.name for c in codebook.codes] == [c.name for c in original_codebook.codes]

    assert "code_Code A" not in new_df.columns
    assert "code_Code B" not in new_df.columns
    assert new_df["code_Combined Code"].tolist() == [1, 1, 1, 0]  # union (OR), not sum
    assert [c.name for c in new_codebook.codes] == ["Combined Code"]
    assert new_codebook.codes[0].merged_from == ["Code A", "Code B"]


def test_merge_codes_ai_proposes_name_when_blank(fake_client, project_cfg, coding_cfg):
    codebook = Codebook.from_dict({"codes": [
        {"name": "Code A", "definition": "a"},
        {"name": "Code B", "definition": "b"},
    ]})
    df = pd.DataFrame({project_cfg.text_column: ["r1", "r2"]})
    df["code_Code A"] = [1, 0]
    df["conf_Code A"] = [0.8, 0.0]
    df["code_Code B"] = [0, 1]
    df["conf_Code B"] = [0.0, 0.7]

    _, new_codebook = merge_codes(df, codebook, fake_client, ["Code A", "Code B"], project_cfg, coding_cfg)

    assert len(new_codebook.codes) == 1
    assert new_codebook.codes[0].name  # AI proposed a non-empty name


# ── split_code validation errors ────────────────────────────────────────────


def test_split_code_raises_when_parent_not_in_codebook(fake_client, project_cfg, coding_cfg):
    codebook, df = _base_codebook_and_df(project_cfg)
    with pytest.raises(ValueError, match="not in codebook"):
        split_code(df, codebook, fake_client, "Nonexistent Parent", project_cfg, coding_cfg)


def test_split_code_raises_when_not_enough_affected_rows(fake_client, project_cfg, coding_cfg):
    other_name = get_default_other_code_name(project_cfg)
    codebook = Codebook.from_dict({"codes": [{"name": "Rare Theme"}, {"name": other_name}]})
    df = pd.DataFrame({project_cfg.text_column: ["r1", "r2"], "code_Rare Theme": [1, 0], f"code_{other_name}": [0, 1]})
    with pytest.raises(ValueError, match="Need >= 2"):
        split_code(df, codebook, fake_client, "Rare Theme", project_cfg, coding_cfg)


def test_split_code_raises_on_duplicate_manual_subcode_names(fake_client, project_cfg, coding_cfg):
    codebook, df = _base_codebook_and_df(project_cfg)
    with pytest.raises(ValueError, match="Duplicate sub-code names"):
        split_code(df, codebook, fake_client, "Broad Theme", project_cfg, coding_cfg, subcodes=["Same", "same"])


def test_split_code_raises_on_name_collision_with_existing_code(fake_client, project_cfg, coding_cfg):
    codebook, df = _base_codebook_and_df(project_cfg)
    other_name = get_default_other_code_name(project_cfg)
    with pytest.raises(ValueError, match="already exist"):
        split_code(df, codebook, fake_client, "Broad Theme", project_cfg, coding_cfg, subcodes=[other_name, "New Sub"])


def test_split_code_raises_when_manual_names_collapse_to_one_after_filtering(fake_client, project_cfg, coding_cfg):
    codebook, df = _base_codebook_and_df(project_cfg)
    with pytest.raises(ValueError, match="Need >= 2 sub-codes"):
        split_code(df, codebook, fake_client, "Broad Theme", project_cfg, coding_cfg, subcodes=["Valid Name", "   "])


def test_split_code_raises_on_definition_length_mismatch(fake_client, project_cfg, coding_cfg):
    codebook, df = _base_codebook_and_df(project_cfg)
    with pytest.raises(ValueError, match="subcode_definitions must be blank"):
        split_code(
            df, codebook, fake_client, "Broad Theme", project_cfg, coding_cfg,
            subcodes=["Sub One", "Sub Two"], subcode_definitions=["only one def"],
        )


def test_split_code_raises_on_missing_definitions_without_enrich(fake_client, project_cfg, coding_cfg):
    codebook, df = _base_codebook_and_df(project_cfg)
    with pytest.raises(ValueError, match="require definitions"):
        split_code(
            df, codebook, fake_client, "Broad Theme", project_cfg, coding_cfg,
            subcodes=["Sub One", "Sub Two"], enrich_subcodes=False,
        )


def test_split_code_ai_proposal_parse_failure_raises(fake_client, project_cfg, coding_cfg):
    cfg = project_cfg.model_copy(update={"survey_context": "AI_SPLIT_PARSE_FAIL"})
    codebook, df = _base_codebook_and_df(cfg)
    with pytest.raises(ValueError, match="no sub-codes"):
        split_code(df, codebook, fake_client, "Broad Theme", cfg, coding_cfg)


def test_split_code_ai_proposal_empty_raises(fake_client, project_cfg, coding_cfg):
    cfg = project_cfg.model_copy(update={"survey_context": "AI_SPLIT_EMPTY"})
    codebook, df = _base_codebook_and_df(cfg)
    with pytest.raises(ValueError, match="no sub-codes"):
        split_code(df, codebook, fake_client, "Broad Theme", cfg, coding_cfg)


def test_split_code_generates_ids_when_codebook_uses_ids(fake_client, project_cfg, coding_cfg):
    other_name = get_default_other_code_name(project_cfg)
    codebook = Codebook.from_dict({"codes": [
        {"name": "Broad Theme", "code_id": "BROAD", "definition": "broad"},
        {"name": other_name, "code_id": "OTHER", "definition": "catch-all"},
    ]})
    texts = [f"response about broad theme number {i}" for i in range(4)]
    df = pd.DataFrame({project_cfg.text_column: texts})
    df["code_Broad Theme"] = [1, 1, 1, 1]
    df["conf_Broad Theme"] = [0.9] * 4
    df[f"code_{other_name}"] = [0, 0, 0, 0]
    df[f"conf_{other_name}"] = [0.0] * 4

    _, new_codebook = split_code(
        df, codebook, fake_client, "Broad Theme", project_cfg, coding_cfg,
        subcodes=["Sub One", "Sub Two"], subcode_ids=["MANUAL_ID", ""], subcode_definitions=["d1", "d2"],
    )

    subcodes = [c for c in new_codebook.codes if c.parent_code == "Broad Theme"]
    assert {c.code_id for c in subcodes} == {"MANUAL_ID", "BROAD_SUB_TWO"}


def test_split_code_raises_on_duplicate_manual_subcode_ids(fake_client, project_cfg, coding_cfg):
    other_name = get_default_other_code_name(project_cfg)
    codebook = Codebook.from_dict({"codes": [
        {"name": "Broad Theme", "code_id": "BROAD", "definition": "broad"},
        {"name": other_name, "code_id": "OTHER", "definition": "catch-all"},
    ]})
    df = pd.DataFrame({project_cfg.text_column: ["r1", "r2"], "code_Broad Theme": [1, 1], f"code_{other_name}": [0, 0]})

    with pytest.raises(ValueError, match="already in the codebook"):
        split_code(
            df, codebook, fake_client, "Broad Theme", project_cfg, coding_cfg,
            subcodes=["Sub One", "Sub Two"], subcode_ids=["OTHER", ""], subcode_definitions=["d1", "d2"],
        )


# ── merge_codes validation errors ───────────────────────────────────────────


def test_merge_codes_raises_when_fewer_than_two_codes(fake_client, project_cfg, coding_cfg):
    df = pd.DataFrame({project_cfg.text_column: ["r1"]})
    codebook = Codebook.from_dict({"codes": [{"name": "Code A"}]})
    with pytest.raises(ValueError, match="Need >= 2"):
        merge_codes(df, codebook, fake_client, ["Code A"], project_cfg, coding_cfg)


def test_merge_codes_raises_when_code_not_in_codebook(fake_client, project_cfg, coding_cfg):
    df = pd.DataFrame({project_cfg.text_column: ["r1"]})
    codebook = Codebook.from_dict({"codes": [{"name": "Code A"}]})
    with pytest.raises(ValueError, match="Not in codebook"):
        merge_codes(df, codebook, fake_client, ["Code A", "Ghost Code"], project_cfg, coding_cfg)


def test_merge_codes_raises_on_name_collision_outside_source_group(fake_client, project_cfg, coding_cfg):
    codebook = Codebook.from_dict({"codes": [
        {"name": "Code A", "definition": "a"}, {"name": "Code B", "definition": "b"}, {"name": "Combined Code", "definition": "existing"},
    ]})
    df = pd.DataFrame({project_cfg.text_column: ["r1", "r2"], "code_Code A": [1, 0], "code_Code B": [0, 1], "code_Combined Code": [0, 0]})

    with pytest.raises(ValueError, match="already exists"):
        merge_codes(df, codebook, fake_client, ["Code A", "Code B"], project_cfg, coding_cfg, merged_name="Combined Code")


def test_merge_codes_raises_on_missing_definition_without_enrich(fake_client, project_cfg, coding_cfg):
    codebook = Codebook.from_dict({"codes": [{"name": "Code A"}, {"name": "Code B"}]})
    df = pd.DataFrame({project_cfg.text_column: ["r1", "r2"], "code_Code A": [1, 0], "code_Code B": [0, 1]})

    with pytest.raises(ValueError, match="requires a definition"):
        merge_codes(df, codebook, fake_client, ["Code A", "Code B"], project_cfg, coding_cfg, merged_name="New Name", enrich_merged=False)


def test_merge_codes_raises_when_coding_columns_missing(fake_client, project_cfg, coding_cfg):
    codebook = Codebook.from_dict({"codes": [{"name": "Code A"}, {"name": "Code B"}]})
    df = pd.DataFrame({project_cfg.text_column: ["r1", "r2"]})  # no code_ columns yet

    with pytest.raises(KeyError):
        merge_codes(df, codebook, fake_client, ["Code A", "Code B"], project_cfg, coding_cfg, merged_name="New Name")


def test_merge_codes_ai_no_name_raises(fake_client, project_cfg, coding_cfg):
    cfg = project_cfg.model_copy(update={"survey_context": "AI_MERGE_NO_NAME"})
    codebook = Codebook.from_dict({"codes": [{"name": "Code A", "definition": "a"}, {"name": "Code B", "definition": "b"}]})
    df = pd.DataFrame({project_cfg.text_column: ["r1", "r2"], "code_Code A": [1, 0], "code_Code B": [0, 1]})

    with pytest.raises(ValueError, match="Model returned no name"):
        merge_codes(df, codebook, fake_client, ["Code A", "Code B"], cfg, coding_cfg)


def test_merge_codes_generates_id_when_codebook_uses_ids(fake_client, project_cfg, coding_cfg):
    codebook = Codebook.from_dict({"codes": [
        {"name": "Code A", "code_id": "A1", "definition": "a"},
        {"name": "Code B", "code_id": "B1", "definition": "b"},
    ]})
    df = pd.DataFrame({project_cfg.text_column: ["r1", "r2"], "code_Code A": [1, 0], "code_Code B": [0, 1]})

    _, new_codebook = merge_codes(df, codebook, fake_client, ["Code A", "Code B"], project_cfg, coding_cfg, merged_name="Combined")

    assert new_codebook.codes[0].code_id
    assert new_codebook.codes[0].merged_from_ids == ["A1", "B1"]

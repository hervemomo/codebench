import os

import openpyxl
import pandas as pd

from codeframe.codebook import Codebook
from codeframe.reporting import cooccurrence_matrix, export_charts, export_workbook, frequency_table


def _coded_df_and_codebook(project_cfg):
    codebook = Codebook.from_dict({"codes": [
        {"name": "Code A", "definition": "a"},
        {"name": "Code B", "definition": "b"},
    ]})
    df = pd.DataFrame({
        "response_id": [1, 2, 3, 4],
        "original_text": ["r1", "r2", "r3", "r4"],
        project_cfg.text_column: ["r1", "r2", "r3", "r4"],
        "is_valid": [True, True, True, True],
        "code_Code A": [1, 1, 0, 0],
        "conf_Code A": [0.9, 0.8, 0.0, 0.0],
        "code_Code B": [0, 1, 1, 0],
        "conf_Code B": [0.0, 0.7, 0.6, 0.0],
    })
    return df, codebook


def test_frequency_table_counts_match_assignments(project_cfg):
    df, codebook = _coded_df_and_codebook(project_cfg)

    freq = frequency_table(df, codebook)

    counts = dict(zip(freq["code"], freq["count"]))
    assert counts["Code A"] == 2
    assert counts["Code B"] == 2
    assert freq["count"].sum() == int(df[["code_Code A", "code_Code B"]].sum().sum())


def test_frequency_table_empty_when_no_code_columns(project_cfg):
    codebook = Codebook.from_dict({"codes": [{"name": "Unused Code"}]})
    df = pd.DataFrame({project_cfg.text_column: ["a", "b"]})

    freq = frequency_table(df, codebook)

    assert freq.empty


def test_cooccurrence_matrix_diagonal_equals_frequency(project_cfg):
    df, codebook = _coded_df_and_codebook(project_cfg)

    cooc = cooccurrence_matrix(df, codebook)

    assert cooc.loc["Code A", "Code A"] == 2
    assert cooc.loc["Code B", "Code B"] == 2
    assert cooc.loc["Code A", "Code B"] == 1  # row 2 carries both


def test_export_workbook_has_five_sheets(tmp_path, project_cfg):
    df, codebook = _coded_df_and_codebook(project_cfg)
    path = tmp_path / "report.xlsx"

    written = export_workbook(df, codebook, path, text_column=project_cfg.text_column)

    wb = openpyxl.load_workbook(written)
    assert wb.sheetnames == ["Summary", "Frequencies", "Co-occurrence", "Codebook", "Coded data"]


def test_export_workbook_summary_counts(tmp_path, project_cfg):
    df, codebook = _coded_df_and_codebook(project_cfg)
    path = tmp_path / "report.xlsx"

    export_workbook(df, codebook, path, text_column=project_cfg.text_column)

    summary = pd.read_excel(path, sheet_name="Summary")
    values = dict(zip(summary["Metric"], summary["Value"]))
    assert values["Total responses"] == 4
    assert values["Code count"] == 2


def test_export_charts_creates_valid_png_files(tmp_path, project_cfg):
    df, codebook = _coded_df_and_codebook(project_cfg)

    outputs = export_charts(df, codebook, tmp_path, file_stem="test")

    freq_path = outputs["frequency_chart"]
    cooc_path = outputs["cooccurrence_chart"]
    assert freq_path is not None and cooc_path is not None

    for p in (freq_path, cooc_path):
        with open(p, "rb") as f:
            magic = f.read(8)
        assert magic.startswith(b"\x89PNG")
        assert os.path.getsize(p) > 1024

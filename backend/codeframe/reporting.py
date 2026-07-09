"""Frequency tables, co-occurrence matrices, and Excel/PNG exports.

Ported from notebook section 0-F. Exports write to a caller-supplied path —
no hard-coded filenames or output directories.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from codeframe.codebook import Codebook  # noqa: E402

logger = logging.getLogger(__name__)


def _code_columns(df: pd.DataFrame, codebook: Codebook) -> list[tuple[str, str]]:
    """Return [(name, code_col)] for every code whose binary column exists in df."""
    return [(c.name, f"code_{c.name}") for c in codebook.codes if f"code_{c.name}" in df.columns]


def frequency_table(df: pd.DataFrame, codebook: Codebook) -> pd.DataFrame:
    """Count how many responses carry each code. Sorted descending by count."""
    entries = _code_columns(df, codebook)
    has_ids = codebook.has_code_ids()
    cols = ["code_id", "code", "count", "percentage"] if has_ids else ["code", "count", "percentage"]
    if not entries:
        return pd.DataFrame(columns=cols)

    total = len(df)
    id_by_name = {c.name: c.code_id for c in codebook.codes}
    rows = []
    for name, code_col in entries:
        count = int(df[code_col].sum())
        row = {"code": name, "count": count, "percentage": round(count / total * 100, 1) if total else 0}
        if has_ids:
            row["code_id"] = id_by_name.get(name, "")
        rows.append(row)
    return pd.DataFrame(rows)[cols].sort_values("count", ascending=False).reset_index(drop=True)


def cooccurrence_matrix(df: pd.DataFrame, codebook: Codebook) -> pd.DataFrame:
    """Code x code co-occurrence matrix. Diagonal = individual code frequency."""
    entries = _code_columns(df, codebook)
    code_cols = [e[1] for e in entries]
    names = [e[0] for e in entries]
    if not code_cols:
        return pd.DataFrame()
    binary = df[code_cols].values.astype(int)
    return pd.DataFrame(binary.T @ binary, index=names, columns=names)


def export_charts(df: pd.DataFrame, codebook: Codebook, output_dir: str | Path, *, file_stem: str = "report") -> dict[str, Optional[str]]:
    """Save a frequency bar chart and a co-occurrence heatmap PNG. Returns {name: path}."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    freq_df = frequency_table(df, codebook)
    cooc_df = cooccurrence_matrix(df, codebook)
    outputs: dict[str, Optional[str]] = {}

    if not freq_df.empty:
        plot_df = freq_df.sort_values("count", ascending=True)
        fig, ax = plt.subplots(figsize=(12, 7))
        colors = sns.color_palette("viridis", len(plot_df))
        bars = ax.barh(plot_df["code"], plot_df["count"], color=colors)
        ax.set_xlabel("Number of responses")
        ax.set_title("Code frequency")
        for bar, pct in zip(bars, plot_df["percentage"]):
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2, f"{pct}%", va="center", fontsize=9)
        plt.tight_layout()
        freq_path = output_dir / f"{file_stem}_frequencies.png"
        plt.savefig(freq_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        outputs["frequency_chart"] = str(freq_path)
    else:
        outputs["frequency_chart"] = None

    if not cooc_df.empty:
        fig, ax = plt.subplots(figsize=(12, 10))
        sns.heatmap(cooc_df, mask=np.eye(len(cooc_df), dtype=bool), annot=True, fmt="d", cmap="YlOrRd", square=True, linewidths=0.5, cbar_kws={"label": "Co-occurrences"}, ax=ax)
        ax.set_title("Code co-occurrence")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        cooc_path = output_dir / f"{file_stem}_cooccurrence.png"
        plt.savefig(cooc_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        outputs["cooccurrence_chart"] = str(cooc_path)
    else:
        outputs["cooccurrence_chart"] = None

    return outputs


def export_workbook(df: pd.DataFrame, codebook: Codebook, path: str | Path, *, text_column: str) -> str:
    """Write a 5-sheet Excel workbook: Summary, Frequencies, Co-occurrence, Codebook, Coded data."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    freq_df = frequency_table(df, codebook)
    cooc_df = cooccurrence_matrix(df, codebook)

    total = len(df)
    n_valid = int(df["is_valid"].sum()) if "is_valid" in df.columns else total
    code_cols = [cc for _, cc in _code_columns(df, codebook)]
    n_coded = int((df[code_cols].sum(axis=1) > 0).sum()) if code_cols else 0
    summary_df = pd.DataFrame({
        "Metric": ["Total responses", "Valid responses", "Invalid/empty", "Coded responses", "Uncoded", "Code count", "Multi-label"],
        "Value": [total, n_valid, total - n_valid, n_coded, total - n_coded, len(codebook.codes), codebook.multi_label],
    })

    has_ids = codebook.has_code_ids()
    codebook_rows = []
    for c in codebook.codes:
        row = {
            "Code ID": c.code_id, "Code": c.name, "Definition": c.definition,
            "Inclusion": "; ".join(c.inclusion_criteria), "Exclusion": "; ".join(c.exclusion_criteria),
            "Examples": " | ".join(c.example_verbatims[:3]),
            "Parent": c.parent_code, "Parent Code ID": c.parent_code_id,
            "Merged from": " | ".join(c.merged_from), "Merged from IDs": " | ".join(c.merged_from_ids),
            "Source": c.source,
        }
        if not has_ids:
            row.pop("Code ID", None)
            row.pop("Parent Code ID", None)
            row.pop("Merged from IDs", None)
        codebook_rows.append(row)
    codebook_df = pd.DataFrame(codebook_rows)

    base_cols = [c for c in ["response_id", "original_text", "codes", "code_ids", "has_multi_label", "num_codes", text_column, "is_valid"] if c in df.columns]
    data_cols = base_cols + [c for c in df.columns if c.startswith("code_")]

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        freq_df.to_excel(writer, sheet_name="Frequencies", index=False)
        cooc_df.to_excel(writer, sheet_name="Co-occurrence")
        codebook_df.to_excel(writer, sheet_name="Codebook", index=False)
        df[data_cols].to_excel(writer, sheet_name="Coded data", index=False)

    logger.info("Workbook written -> %s", path)
    return str(path)

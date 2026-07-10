"""Shared helpers for split/merge/results/export: reconstruct a run's coded
dataframe (the `code_<name>`/`conf_<name>` shape codeframe.coding/refine/
reporting all expect) from persisted CodeAssignment rows, since Sequence 4
only ever wrote those rows -- it never kept the intermediate pandas frame.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.scoped import scoped_query
from app.models import CodeAssignment, CodingRun, Response
from codeframe.codebook import Codebook
from codeframe.coding import add_codes_column
from codeframe.config import CodingConfig, ProjectConfig


def build_llm_client(project_cfg: ProjectConfig):
    if get_settings().fake_llm:
        from tests.fixtures.fake_openai import FakeOpenAI

        return FakeOpenAI()

    from openai import OpenAI

    return OpenAI(api_key=get_settings().require_openai_api_key(), timeout=project_cfg.openai_timeout_seconds)


def project_cfg_for(run: CodingRun) -> ProjectConfig:
    project = run.question.project
    return ProjectConfig(
        survey_context=project.context,
        source_language_code=project.source_lang,
        target_language_code=project.target_lang,
        codebook_language_code=project.codebook_lang,
    )


def accepted_codebook(run: CodingRun) -> Codebook:
    accepted = [c for c in run.codebook_json.get("codes", []) if c.get("status") == "accepted"]
    return Codebook.from_dict({**run.codebook_json, "codes": accepted})


def build_coded_dataframe(session: Session, org_id: int, run: CodingRun) -> tuple[pd.DataFrame, Codebook, ProjectConfig, CodingConfig]:
    """Rebuild the coded dataframe for an APPLIED run: one row per valid
    Response in the run's dataset, with code_<name>/conf_<name> columns
    populated from that run's CodeAssignment rows, plus the summary
    codes/code_ids/num_codes/has_multi_label columns."""
    project_cfg = project_cfg_for(run)
    coding_cfg = CodingConfig()
    codebook = accepted_codebook(run)

    dataset_id = run.config_json["dataset_id"]
    responses = list(session.scalars(
        scoped_query(session, Response, org_id).where(
            Response.dataset_id == dataset_id, Response.is_valid.is_(True)
        )
    ).all())

    df = pd.DataFrame({
        "response_id": [r.id for r in responses],
        project_cfg.text_column: [r.translated_text for r in responses],
    })
    for code in codebook.codes:
        df[f"code_{code.name}"] = 0
        df[f"conf_{code.name}"] = 0.0

    name_by_code_id = {c.code_id: c.name for c in codebook.codes}
    row_by_response_id = {r.id: i for i, r in enumerate(responses)}

    assignments = list(session.scalars(
        scoped_query(session, CodeAssignment, org_id).where(CodeAssignment.run_id == run.id)
    ).all())
    for a in assignments:
        name = name_by_code_id.get(a.code_id)
        row = row_by_response_id.get(a.response_id)
        if name is None or row is None:
            continue
        df.at[row, f"code_{name}"] = 1
        df.at[row, f"conf_{name}"] = a.confidence

    df = add_codes_column(df, codebook)
    return df, codebook, project_cfg, coding_cfg


def stage_assignments_from_dataframe(df: pd.DataFrame, codebook: Codebook) -> list[dict]:
    """Flatten a coded dataframe's code_<name> columns into per-(response,
    code) tuples, keyed by the codebook's stable code_id -- the shape
    app/jobs/apply.py's kind=SPLIT/MERGE branch consumes at apply time,
    filtered down to whatever is still "accepted" after review."""
    staged: list[dict] = []
    for code in codebook.codes:
        col = f"code_{code.name}"
        conf_col = f"conf_{code.name}"
        if col not in df.columns:
            continue
        matched = df[df[col] == 1]
        for _, row in matched.iterrows():
            staged.append({
                "response_id": int(row["response_id"]),
                "code_id": code.code_id,
                "confidence": float(row.get(conf_col, 0.0) or 0.0),
            })
    return staged

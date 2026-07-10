"""Results (frequencies/co-occurrence/codebook, paginated+searchable coded
responses) and exports (async job -> ExportArtifact in MinIO -> presigned URL).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import storage
from app.auth import CurrentUser, get_current_user
from app.db.base import get_db_session
from app.db.scoped import scoped_query
from app.jobs.exports import run_export_job
from app.jobs.queue import get_queue
from app.jobs.refine_common import build_coded_dataframe
from app.models import CodingRunStatus, ExportArtifact
from app.routers.coding import get_run_or_404
from codeframe import reporting

router = APIRouter(prefix="/api", tags=["results"])

ExportFormat = Literal["xlsx", "csv_frequencies", "csv_coded", "png_frequencies", "png_cooccurrence"]


def _require_applied(run):
    if run.status != CodingRunStatus.APPLIED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Results are available once the run has been applied.")


@router.get("/runs/{run_id}/results/frequencies")
def get_frequencies(run_id: int, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)):
    run = get_run_or_404(session, current.org_id, run_id)
    _require_applied(run)
    df, codebook, _project_cfg, _coding_cfg = build_coded_dataframe(session, current.org_id, run)
    return {"frequencies": reporting.frequency_table(df, codebook).to_dict(orient="records")}


@router.get("/runs/{run_id}/results/cooccurrence")
def get_cooccurrence(run_id: int, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)):
    run = get_run_or_404(session, current.org_id, run_id)
    _require_applied(run)
    df, codebook, _project_cfg, _coding_cfg = build_coded_dataframe(session, current.org_id, run)
    cooc = reporting.cooccurrence_matrix(df, codebook)
    return {"codes": cooc.index.tolist(), "matrix": cooc.values.tolist()}


@router.get("/runs/{run_id}/results/codebook")
def get_results_codebook(run_id: int, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)):
    run = get_run_or_404(session, current.org_id, run_id)
    _require_applied(run)
    accepted = [c for c in run.codebook_json.get("codes", []) if c.get("status") == "accepted"]
    return {"codes": accepted}


@router.get("/runs/{run_id}/responses")
def list_responses(
    run_id: int, search: str = "", code: str = "", page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=200),
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    run = get_run_or_404(session, current.org_id, run_id)
    _require_applied(run)
    df, codebook, project_cfg, _coding_cfg = build_coded_dataframe(session, current.org_id, run)

    if search:
        df = df[df[project_cfg.text_column].str.contains(search, case=False, na=False, regex=False)]
    if code:
        name_by_id = {c.code_id: c.name for c in codebook.codes}
        col = f"code_{name_by_id[code]}" if code in name_by_id else None
        df = df[df[col] == 1] if col and col in df.columns else df.iloc[0:0]

    total = len(df)
    start = (page - 1) * page_size
    page_df = df.iloc[start : start + page_size]
    items = [
        {
            "response_id": int(row["response_id"]),
            "text": row[project_cfg.text_column],
            "codes": [c for c in str(row.get("codes", "")).split(" | ") if c],
            "num_codes": int(row.get("num_codes", 0)),
        }
        for _, row in page_df.iterrows()
    ]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/runs/{run_id}/exports", status_code=status.HTTP_202_ACCEPTED)
def create_export(
    run_id: int, format: ExportFormat,
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    run = get_run_or_404(session, current.org_id, run_id)
    _require_applied(run)
    job = get_queue().enqueue(run_export_job, run.id, current.org_id, format, job_timeout=900)
    return {"job_id": job.id}


@router.get("/exports/{artifact_id}")
def get_export(artifact_id: int, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)):
    artifact = session.scalars(
        scoped_query(session, ExportArtifact, current.org_id).where(ExportArtifact.id == artifact_id)
    ).one_or_none()
    if artifact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export artifact not found")
    return {"id": artifact.id, "kind": artifact.kind, "url": storage.presign_url(artifact.file_key)}

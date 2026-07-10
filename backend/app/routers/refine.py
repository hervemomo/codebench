"""Refinement: split/merge as new child CodingRuns (review + apply reuse
app/routers/coding.py's existing DRAFT->REVIEWED->APPLIED endpoints
unchanged -- only run creation differs), and lineage reset.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.db.base import get_db_session
from app.db.scoped import scoped_query
from app.jobs.queue import get_queue
from app.jobs.refine import run_propose_merge_job, run_propose_split_job
from app.models import CodingRun, CodingRunKind, CodingRunStatus
from app.routers.coding import get_run_or_404
from app.routers.datasets import get_question_or_404

router = APIRouter(prefix="/api", tags=["refine"])


class ParentSplitConfig(BaseModel):
    parent_code_id: str
    subcodes: Optional[list[str]] = None
    subcode_definitions: Optional[list[str]] = None
    n_proposed: Optional[int] = None
    preserve_parent: bool = False
    enrich_subcodes: bool = True


class SplitRequest(BaseModel):
    # Single-parent shorthand (most common case): parent_code_id + the rest
    # of ParentSplitConfig's fields at the top level.
    parent_code_id: Optional[str] = None
    subcodes: Optional[list[str]] = None
    subcode_definitions: Optional[list[str]] = None
    n_proposed: Optional[int] = None
    preserve_parent: bool = False
    enrich_subcodes: bool = True
    # Multi-config: split several DIFFERENT parent codes in one request, each
    # into its own independent child run ("multi-config splits create one
    # child run each"). Takes precedence over the shorthand fields above.
    parent_codes: Optional[list[ParentSplitConfig]] = None


def _accepted_code_ids(run: CodingRun) -> set[str]:
    return {c["code_id"] for c in run.codebook_json.get("codes", []) if c.get("status") == "accepted"}


@router.post("/runs/{run_id}/split", status_code=status.HTTP_202_ACCEPTED)
def split_run(
    run_id: int, payload: SplitRequest,
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    parent = get_run_or_404(session, current.org_id, run_id)
    if parent.status != CodingRunStatus.APPLIED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Parent run must be APPLIED before it can be split.")

    if payload.parent_codes:
        configs = payload.parent_codes
    elif payload.parent_code_id:
        configs = [ParentSplitConfig(
            parent_code_id=payload.parent_code_id, subcodes=payload.subcodes,
            subcode_definitions=payload.subcode_definitions, n_proposed=payload.n_proposed,
            preserve_parent=payload.preserve_parent, enrich_subcodes=payload.enrich_subcodes,
        )]
    else:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Provide parent_code_id or parent_codes.")

    accepted_ids = _accepted_code_ids(parent)
    unknown = [cfg.parent_code_id for cfg in configs if cfg.parent_code_id not in accepted_ids]
    if unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"parent_code_id(s) not found among the parent run's accepted codes: {unknown}")

    created = []
    for cfg in configs:
        child = CodingRun(
            org_id=current.org_id, question_id=parent.question_id, parent_run_id=parent.id,
            kind=CodingRunKind.SPLIT, status=CodingRunStatus.DRAFT,
            config_json={
                "parent_run_id": parent.id, "dataset_id": parent.config_json["dataset_id"],
                "parent_code_id": cfg.parent_code_id,
                "subcodes": cfg.subcodes, "subcode_definitions": cfg.subcode_definitions,
                "n_proposed": cfg.n_proposed, "preserve_parent": cfg.preserve_parent,
                "enrich_subcodes": cfg.enrich_subcodes,
            },
            codebook_json={}, token_usage={},
        )
        session.add(child)
        session.commit()
        session.refresh(child)
        job = get_queue().enqueue(run_propose_split_job, child.id, current.org_id, job_timeout=900)
        created.append({"id": child.id, "job_id": job.id, "parent_code_id": cfg.parent_code_id})

    return {"parent_id": parent.id, "runs": created}


class MergeRequest(BaseModel):
    code_ids: list[str] = Field(min_length=2)
    merged_name: Optional[str] = None
    merged_code_id: Optional[str] = None
    merged_definition: Optional[str] = None
    enrich_merged: bool = True


@router.post("/runs/{run_id}/merge", status_code=status.HTTP_202_ACCEPTED)
def merge_run(
    run_id: int, payload: MergeRequest,
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    parent = get_run_or_404(session, current.org_id, run_id)
    if parent.status != CodingRunStatus.APPLIED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Parent run must be APPLIED before it can be merged.")
    missing = [cid for cid in payload.code_ids if cid not in _accepted_code_ids(parent)]
    if missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"code_ids not found among the parent run's accepted codes: {missing}")

    child = CodingRun(
        org_id=current.org_id, question_id=parent.question_id, parent_run_id=parent.id,
        kind=CodingRunKind.MERGE, status=CodingRunStatus.DRAFT,
        config_json={
            "parent_run_id": parent.id, "dataset_id": parent.config_json["dataset_id"],
            "code_ids": payload.code_ids, "merged_name": payload.merged_name,
            "merged_code_id": payload.merged_code_id, "merged_definition": payload.merged_definition,
            "enrich_merged": payload.enrich_merged,
        },
        codebook_json={}, token_usage={},
    )
    session.add(child)
    session.commit()
    session.refresh(child)
    job = get_queue().enqueue(run_propose_merge_job, child.id, current.org_id, job_timeout=900)
    return {"id": child.id, "job_id": job.id}


@router.post("/questions/{question_id}/reset")
def reset_question(
    question_id: int, to_run: int = Query(...),
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    question = get_question_or_404(session, current.org_id, question_id)
    target = session.scalars(scoped_query(session, CodingRun, current.org_id).where(CodingRun.id == to_run)).one_or_none()
    if target is None or target.question_id != question.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found for this question.")
    if target.status != CodingRunStatus.APPLIED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Can only reset to an APPLIED run.")

    # Bookkeeping only -- nothing is deleted. Later runs in whatever branch
    # was previously active stay fully intact and queryable; a new split/merge
    # off `target` (or any other run) just creates another child alongside them.
    question.active_run_id = target.id
    session.commit()
    return {"question_id": question.id, "active_run_id": question.active_run_id}

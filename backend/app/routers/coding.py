"""The Code stage: codebook generation runs, the DRAFT->REVIEWED->APPLIED
human review gate, batch coding apply, and QA metrics.

POST /api/questions/{id}/runs         enqueue codebook generation (ai|import)
GET  /api/runs/{id}                   run detail (status, codebook, tokens)
PATCH /api/runs/{id}/codes/{code_id}  accept/reject/edit one proposed code
POST /api/runs/{id}/codes             manually add a code
POST /api/runs/{id}/finalize          DRAFT -> REVIEWED (409 if codes pending)
POST /api/runs/{id}/apply             REVIEWED -> enqueue apply job -> APPLIED
GET  /api/runs/{id}/qa                QA Review page metrics

All lookups go through scoped_query so cross-org IDs 404. `codebook_json` is
mutated in place in a few places (accept/reject/add/finalize); every such
mutation is followed by flag_modified(run, "codebook_json") since SQLAlchemy
doesn't track in-place JSONB changes on its own.
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.auth import CurrentUser, get_current_user
from app.db.base import get_db_session
from app.db.scoped import scoped_query
from app.jobs.apply import run_apply_job
from app.jobs.codebook import run_create_codebook_job
from app.jobs.queue import get_queue
from app.models import CodeAssignment, CodingRun, CodingRunKind, CodingRunStatus, Dataset, Response
from app.qa import compute_qa_metrics
from app.routers.datasets import get_question_or_404
from codeframe.codebook import Codebook, Code as CFCode, auto_code_id_for_new_code, ensure_other_code, get_default_other_code_name
from codeframe.config import ProjectConfig

router = APIRouter(prefix="/api", tags=["coding"])


def get_run_or_404(session: Session, org_id: int, run_id: int) -> CodingRun:
    run = session.scalars(scoped_query(session, CodingRun, org_id).where(CodingRun.id == run_id)).one_or_none()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _project_cfg_for(run: CodingRun) -> ProjectConfig:
    project = run.question.project
    return ProjectConfig(
        survey_context=project.context,
        source_language_code=project.source_lang,
        target_language_code=project.target_lang,
        codebook_language_code=project.codebook_lang,
    )


def _next_code_id(existing_ids: set[str], name: str) -> str:
    """Reuse codeframe's slug/uniqueness logic without a full Codebook of real codes."""
    temp_cb = Codebook(codes=[CFCode(code_id=cid, name="") for cid in existing_ids])
    return auto_code_id_for_new_code(temp_cb, name)


def _run_out(run: CodingRun) -> dict:
    return {
        "id": run.id,
        "question_id": run.question_id,
        "kind": run.kind.value,
        "status": run.status.value,
        "codebook": run.codebook_json,
        "token_usage": run.token_usage,
        "config": run.config_json,
    }


# ── Run creation ─────────────────────────────────────────────────────────────


class RunCreate(BaseModel):
    kind: Literal["ai", "import"]
    target_codes: Optional[int] = None
    cluster_overrides: Optional[dict] = None
    codebook_source: Optional[Union[list, dict]] = None
    enrich: bool = False


@router.post("/questions/{question_id}/runs", status_code=status.HTTP_202_ACCEPTED)
def create_run(
    question_id: int, payload: RunCreate,
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    question = get_question_or_404(session, current.org_id, question_id)
    if payload.kind == "import" and payload.codebook_source is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "codebook_source is required for kind=import")

    dataset = session.scalars(
        scoped_query(session, Dataset, current.org_id)
        .where(Dataset.question_id == question.id, Dataset.status == "preprocessed")
        .order_by(Dataset.created_at.desc(), Dataset.id.desc())
    ).first()
    if dataset is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No preprocessed dataset is ready for this question.")

    run = CodingRun(
        org_id=current.org_id, question_id=question.id,
        kind=CodingRunKind.S2 if payload.kind == "ai" else CodingRunKind.S3,
        status=CodingRunStatus.DRAFT,
        config_json={
            "kind": payload.kind, "dataset_id": dataset.id, "target_codes": payload.target_codes,
            "cluster_overrides": payload.cluster_overrides, "codebook_source": payload.codebook_source,
            "enrich": payload.enrich,
        },
        codebook_json={}, token_usage={},
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    job = get_queue().enqueue(run_create_codebook_job, run.id, current.org_id, job_timeout=900)
    return {"id": run.id, "status": run.status.value, "kind": payload.kind, "job_id": job.id}


@router.get("/runs/{run_id}")
def get_run(run_id: int, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)):
    return _run_out(get_run_or_404(session, current.org_id, run_id))


# ── Review workflow ──────────────────────────────────────────────────────────


class CodePatch(BaseModel):
    status: Optional[Literal["accepted", "rejected"]] = None
    name: Optional[str] = None
    definition: Optional[str] = None


@router.patch("/runs/{run_id}/codes/{code_id}")
def patch_code(
    run_id: int, code_id: str, payload: CodePatch,
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    run = get_run_or_404(session, current.org_id, run_id)
    if run.status != CodingRunStatus.DRAFT:
        raise HTTPException(status.HTTP_409_CONFLICT, "Codes can only be edited while the run is in DRAFT status.")

    codes = run.codebook_json.get("codes", [])
    code = next((c for c in codes if c.get("code_id") == code_id), None)
    if code is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Code not found in this run.")

    if payload.status is not None:
        code["status"] = payload.status
    if payload.name is not None:
        code["name"] = payload.name
    if payload.definition is not None:
        code["definition"] = payload.definition

    flag_modified(run, "codebook_json")
    session.commit()
    session.refresh(run)
    return _run_out(run)


class CodeCreate(BaseModel):
    name: str = Field(min_length=1)
    definition: str = ""
    inclusion_criteria: list[str] = Field(default_factory=list)
    exclusion_criteria: list[str] = Field(default_factory=list)
    example_verbatims: list[str] = Field(default_factory=list)


@router.post("/runs/{run_id}/codes", status_code=status.HTTP_201_CREATED)
def add_code(
    run_id: int, payload: CodeCreate,
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    run = get_run_or_404(session, current.org_id, run_id)
    if run.status != CodingRunStatus.DRAFT:
        raise HTTPException(status.HTTP_409_CONFLICT, "Codes can only be added while the run is in DRAFT status.")

    codes = run.codebook_json.setdefault("codes", [])
    existing_ids = {c["code_id"] for c in codes if c.get("code_id")}
    codes.append({
        "code_id": _next_code_id(existing_ids, payload.name),
        "name": payload.name,
        "definition": payload.definition,
        "inclusion_criteria": payload.inclusion_criteria,
        "exclusion_criteria": payload.exclusion_criteria,
        "example_verbatims": payload.example_verbatims,
        "status": "accepted",
        "source": "manual",
    })
    flag_modified(run, "codebook_json")
    session.commit()
    session.refresh(run)
    return _run_out(run)


@router.post("/runs/{run_id}/finalize")
def finalize_run(run_id: int, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)):
    run = get_run_or_404(session, current.org_id, run_id)
    if run.status != CodingRunStatus.DRAFT:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Run must be in DRAFT status to finalize (currently {run.status.value}).")

    codes = run.codebook_json.get("codes", [])
    proposed = [c["name"] for c in codes if c.get("status") == "proposed"]
    if proposed:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot finalize: codes still pending review: {proposed}")

    accepted = [c for c in codes if c.get("status") == "accepted"]
    project_cfg = _project_cfg_for(run)
    other_name = get_default_other_code_name(project_cfg)
    has_catch_all = any(c["name"].strip().casefold() == other_name.strip().casefold() for c in accepted)

    if not has_catch_all:
        existing_ids = {c["code_id"] for c in codes if c.get("code_id")}
        new_id = _next_code_id(existing_ids, other_name)
        # Empty scratch codebook (no manual code_ids on it) so ensure_other_code
        # doesn't think this codebook "requires_manual_ids" and demand one back.
        temp_cb = ensure_other_code(project_cfg, Codebook(codes=[]), other_name=other_name, other_code_id=new_id)
        new_other = temp_cb.codes[-1]
        d = new_other.to_dict()
        d["status"] = "accepted"
        d["source"] = "system_catch_all"
        codes.append(d)

    flag_modified(run, "codebook_json")
    run.status = CodingRunStatus.REVIEWED
    session.commit()
    session.refresh(run)
    return _run_out(run)


@router.post("/runs/{run_id}/apply", status_code=status.HTTP_202_ACCEPTED)
def apply_run(run_id: int, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)):
    run = get_run_or_404(session, current.org_id, run_id)
    if run.status not in (CodingRunStatus.REVIEWED, CodingRunStatus.APPLIED):
        # REVIEWED: normal first apply. APPLIED: re-apply is allowed and safe
        # (app/jobs/apply.py deletes prior assignments before inserting).
        raise HTTPException(status.HTTP_409_CONFLICT, f"Run must be REVIEWED before it can be applied (currently {run.status.value}).")

    job = get_queue().enqueue(run_apply_job, run.id, current.org_id, job_timeout=900)
    return {"job_id": job.id}


# ── QA ────────────────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}/qa")
def run_qa(run_id: int, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)):
    run = get_run_or_404(session, current.org_id, run_id)
    if run.status != CodingRunStatus.APPLIED:
        raise HTTPException(status.HTTP_409_CONFLICT, "QA metrics are available once the run has been applied.")

    dataset_id = run.config_json["dataset_id"]
    valid_responses = list(session.scalars(
        scoped_query(session, Response, current.org_id).where(
            Response.dataset_id == dataset_id, Response.is_valid.is_(True)
        )
    ).all())
    valid_ids = [r.id for r in valid_responses]
    text_by_id = {r.id: r.translated_text for r in valid_responses}

    assignment_rows = list(session.scalars(
        scoped_query(session, CodeAssignment, current.org_id).where(CodeAssignment.run_id == run.id)
    ).all())

    accepted_codes = [c for c in run.codebook_json.get("codes", []) if c.get("status") == "accepted"]
    other_name = get_default_other_code_name(_project_cfg_for(run))
    name_by_id = {c["code_id"]: c["name"] for c in accepted_codes}
    codes_meta = [
        {
            "code_id": c["code_id"], "name": c["name"],
            "is_catch_all": c["name"].strip().casefold() == other_name.strip().casefold(),
        }
        for c in accepted_codes
    ]

    assignments = [
        {
            "response_id": a.response_id, "code_id": a.code_id,
            "code_name": name_by_id.get(a.code_id, a.code_id),
            "confidence": a.confidence, "text": text_by_id.get(a.response_id, ""),
        }
        for a in assignment_rows
    ]

    return compute_qa_metrics(valid_response_ids=valid_ids, assignments=assignments, codes=codes_meta)

"""POST /api/questions/{id}/datasets (upload + preview), POST /api/datasets/{id}/preprocess
(enqueue RQ job), GET /api/datasets/{id}/stats.
"""

from __future__ import annotations

import io
import uuid
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import storage
from app.auth import CurrentUser, get_current_user
from app.db.base import get_db_session
from app.db.scoped import scoped_query
from app.jobs.preprocess import run_preprocess_job
from app.jobs.queue import get_queue
from app.models import Dataset, Question, Response

router = APIRouter(prefix="/api", tags=["datasets"])

_SUPPORTED_SUFFIXES = {".xlsx", ".xls", ".csv"}


def get_question_or_404(session: Session, org_id: int, question_id: int) -> Question:
    question = session.scalars(
        scoped_query(session, Question, org_id).where(Question.id == question_id)
    ).one_or_none()
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question


def get_dataset_or_404(session: Session, org_id: int, dataset_id: int) -> Dataset:
    dataset = session.scalars(
        scoped_query(session, Dataset, org_id).where(Dataset.id == dataset_id)
    ).one_or_none()
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")
    return dataset


def _read_preview(content: bytes, filename: str, sheet=0) -> tuple[list[str], list[dict]]:
    import pandas as pd

    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in _SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Unsupported file type: {suffix or filename}")

    buf = io.BytesIO(content)
    df = pd.read_excel(buf, sheet_name=sheet) if suffix in (".xlsx", ".xls") else pd.read_csv(buf)
    columns = [str(c) for c in df.columns]
    preview = df.head(10).fillna("").astype(str).to_dict(orient="records")
    return columns, preview


@router.post("/questions/{question_id}/datasets", status_code=status.HTTP_201_CREATED)
async def upload_dataset(
    question_id: int, file: UploadFile,
    current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session),
):
    question = get_question_or_404(session, current.org_id, question_id)
    content = await file.read()
    columns, preview = _read_preview(content, file.filename or "upload.xlsx")

    key = f"datasets/org-{current.org_id}/question-{question.id}/{uuid.uuid4()}-{file.filename}"
    storage.put_object(key, content, content_type=file.content_type)

    dataset = Dataset(org_id=current.org_id, question_id=question.id, file_key=key, sheet="0", status="uploaded")
    session.add(dataset)
    session.commit()
    session.refresh(dataset)

    return {"id": dataset.id, "file_key": dataset.file_key, "status": dataset.status, "columns": columns, "preview": preview}


@router.post("/datasets/{dataset_id}/preprocess", status_code=status.HTTP_202_ACCEPTED)
def enqueue_preprocess(
    dataset_id: int, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)
):
    dataset = get_dataset_or_404(session, current.org_id, dataset_id)
    job = get_queue().enqueue(run_preprocess_job, dataset.id, current.org_id, job_timeout=600)
    return {"job_id": job.id}


class StatsOut(BaseModel):
    total: int
    kept: int
    invalid: int
    duplicates: int
    invalid_reasons: dict[str, int]
    sample_removed: list[str]


@router.get("/datasets/{dataset_id}/stats", response_model=StatsOut)
def dataset_stats(
    dataset_id: int, current: CurrentUser = Depends(get_current_user), session: Session = Depends(get_db_session)
):
    dataset = get_dataset_or_404(session, current.org_id, dataset_id)
    responses = list(session.scalars(
        scoped_query(session, Response, current.org_id).where(Response.dataset_id == dataset.id)
    ).all())

    kept = sum(1 for r in responses if r.is_valid)
    invalid = sum(1 for r in responses if r.invalid_reason and "invalid" in r.invalid_reason)
    duplicates = sum(1 for r in responses if r.invalid_reason and "duplicate" in r.invalid_reason)
    reasons = Counter(r.invalid_reason for r in responses if not r.is_valid)
    sample_removed = [r.raw_text for r in responses if not r.is_valid][:10]

    return StatsOut(
        total=len(responses), kept=kept, invalid=invalid, duplicates=duplicates,
        invalid_reasons=dict(reasons), sample_removed=sample_removed,
    )

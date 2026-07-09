"""RQ job: load a dataset's raw file, run codeframe preprocessing + translation,
write Response rows, and update Dataset.status.

Progress is appended (RPUSH) as JSON snapshots to the Redis list
`progress:{job_id}` — see app/routers/jobs.py for how GET /api/jobs/{id} and
the SSE stream read it back.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional

from rq import get_current_job
from sqlalchemy import delete

from app import storage
from app.config import get_settings
from app.db.base import SessionLocal
from app.db.scoped import scoped_query
from app.jobs.queue import get_redis_client
from app.models import Dataset, Response
from codeframe.config import CodingConfig, PreprocessConfig, ProjectConfig
from codeframe.preprocessing import load_survey_data, preprocess as codeframe_preprocess
from codeframe.translation import translate_records

_TOTAL_STAGES = 4


def progress_key(job_id: str) -> str:
    return f"progress:{job_id}"


def _push_progress(redis_client, job_id: str, stage: str, current: int) -> None:
    redis_client.rpush(
        progress_key(job_id),
        json.dumps({"stage": stage, "current": current, "total": _TOTAL_STAGES}),
    )


def _build_llm_client(project_cfg: ProjectConfig):
    if get_settings().fake_llm:
        from tests.fixtures.fake_openai import FakeOpenAI

        return FakeOpenAI()

    from openai import OpenAI

    return OpenAI(api_key=get_settings().require_openai_api_key(), timeout=project_cfg.openai_timeout_seconds)


def run_preprocess_job(dataset_id: int, org_id: int, job_id: Optional[str] = None) -> dict:
    """Entry point enqueued via app.jobs.queue.get_queue(). Safe to call directly
    (job_id defaults to a fixed sync marker) for tests that don't go through RQ."""
    job = get_current_job()
    job_id = job_id or (job.id if job else "sync")
    redis_client = get_redis_client()

    session = SessionLocal()
    try:
        dataset = session.scalars(
            scoped_query(session, Dataset, org_id).where(Dataset.id == dataset_id)
        ).one_or_none()
        if dataset is None:
            raise ValueError(f"Dataset {dataset_id} not found for org {org_id}")
        question = dataset.question
        project = question.project

        _push_progress(redis_client, job_id, "loading", 0)
        raw_bytes = storage.get_object(dataset.file_key)
        sheet = int(dataset.sheet) if dataset.sheet.isdigit() else dataset.sheet
        # load_survey_data() wants a filesystem path (mirrors the notebook's
        # design); the file only exists as bytes in MinIO, so stage it locally.
        suffix = Path(dataset.file_key).suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(raw_bytes)
            tmp.flush()
            df = load_survey_data(tmp.name, question.survey_col, sheet_name=sheet)
        _push_progress(redis_client, job_id, "loaded", 1)

        preprocess_cfg = PreprocessConfig()
        result = codeframe_preprocess(df, preprocess_cfg)
        _push_progress(redis_client, job_id, "preprocessed", 2)

        project_cfg = ProjectConfig(
            survey_context=project.context,
            source_language_code=project.source_lang,
            target_language_code=project.target_lang,
            codebook_language_code=project.codebook_lang,
        )
        coding_cfg = CodingConfig()
        client = _build_llm_client(project_cfg)
        translated = translate_records(result.kept, project_cfg, coding_cfg, client)
        _push_progress(redis_client, job_id, "translated", 3)

        # Re-running preprocess on the same dataset (retry, worker restart, or a
        # deliberate re-run) must not duplicate rows — clear any prior output first.
        session.execute(delete(Response).where(Response.dataset_id == dataset.id, Response.org_id == org_id))

        for _, row in translated.iterrows():
            session.add(Response(
                org_id=org_id, dataset_id=dataset.id,
                raw_text=str(row.get("original_text", "")), clean_text=str(row.get("cleaned_text", "")),
                translated_text=str(row.get(project_cfg.text_column, "")),
                is_valid=True, invalid_reason=None,
            ))

        invalid_idx = set(result.invalid.index)
        duplicate_idx = set(result.duplicates.index)
        for idx in invalid_idx | duplicate_idx:
            reasons = [r for r, present in (("invalid", idx in invalid_idx), ("duplicate", idx in duplicate_idx)) if present]
            row = df.loc[idx]
            session.add(Response(
                org_id=org_id, dataset_id=dataset.id,
                raw_text=str(row.get("original_text", "")), clean_text="", translated_text="",
                is_valid=False, invalid_reason=",".join(reasons),
            ))

        dataset.status = "preprocessed"
        session.commit()

        _push_progress(redis_client, job_id, "done", 4)
        return {"kept": len(result.kept), "invalid": len(result.invalid), "duplicates": len(result.duplicates)}
    finally:
        session.close()

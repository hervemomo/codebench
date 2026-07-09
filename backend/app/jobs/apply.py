"""RQ job: apply a REVIEWED run's accepted codes to its dataset's responses.

Writes one CodeAssignment row per (response, accepted code) the coder
returned, records aggregate token usage on the run, and flips the run to
APPLIED. Re-running (retry, worker restart, deliberate re-run) must not
duplicate assignments -- see Sequence 3's preprocess-job idempotency lesson
in HANDOFF.md -- so existing assignments for this run are cleared first.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
from rq import get_current_job
from sqlalchemy import delete

from app.config import get_settings
from app.db.base import SessionLocal
from app.db.scoped import scoped_query
from app.jobs.progress import push_progress
from app.jobs.queue import get_redis_client
from app.models import CodeAssignment, CodingRun, CodingRunStatus, Response
from codeframe.codebook import Codebook
from codeframe.coding import apply_codes
from codeframe.config import CodingConfig, ProjectConfig


def _build_llm_client(project_cfg: ProjectConfig):
    if get_settings().fake_llm:
        from tests.fixtures.fake_openai import FakeOpenAI

        return FakeOpenAI()

    from openai import OpenAI

    return OpenAI(api_key=get_settings().require_openai_api_key(), timeout=project_cfg.openai_timeout_seconds)


def run_apply_job(run_id: int, org_id: int, job_id: Optional[str] = None) -> dict:
    job = get_current_job()
    job_id = job_id or (job.id if job else "sync")
    redis_client = get_redis_client()

    session = SessionLocal()
    try:
        run = session.scalars(scoped_query(session, CodingRun, org_id).where(CodingRun.id == run_id)).one_or_none()
        if run is None:
            raise ValueError(f"CodingRun {run_id} not found for org {org_id}")
        if run.status not in (CodingRunStatus.REVIEWED, CodingRunStatus.APPLIED):
            # REVIEWED: normal first apply. APPLIED: a safe re-run (retry, worker
            # restart, deliberate re-apply) -- idempotent via delete-then-insert
            # below, same pattern as app/jobs/preprocess.py's dataset re-run fix.
            raise ValueError(f"CodingRun {run_id} must be REVIEWED or APPLIED to apply (status={run.status.value}).")

        question = run.question
        project = question.project
        dataset_id = run.config_json["dataset_id"]

        accepted = [c for c in run.codebook_json.get("codes", []) if c.get("status") == "accepted"]
        codebook_obj = Codebook.from_dict({**run.codebook_json, "codes": accepted})
        code_id_by_name = {c["name"]: c["code_id"] for c in accepted}

        responses = list(session.scalars(
            scoped_query(session, Response, org_id).where(
                Response.dataset_id == dataset_id, Response.is_valid.is_(True)
            )
        ).all())

        project_cfg = ProjectConfig(
            survey_context=project.context,
            source_language_code=project.source_lang,
            target_language_code=project.target_lang,
            codebook_language_code=project.codebook_lang,
        )
        coding_cfg = CodingConfig()
        client = _build_llm_client(project_cfg)

        push_progress(redis_client, job_id, "coding", 0, max(1, len(responses)))
        df = pd.DataFrame({
            "response_id": [r.id for r in responses],
            project_cfg.text_column: [r.translated_text for r in responses],
        })

        usage_log: list[dict] = []

        def _progress_cb(batch_i: int, n_batches: int) -> None:
            push_progress(redis_client, job_id, "coding", batch_i, max(1, n_batches))

        coded_df = apply_codes(
            df, codebook_obj, project_cfg, coding_cfg, client, progress_cb=_progress_cb, usage_log=usage_log
        )

        push_progress(redis_client, job_id, "assigning", 0, max(1, len(coded_df)))
        session.execute(delete(CodeAssignment).where(CodeAssignment.run_id == run.id, CodeAssignment.org_id == org_id))

        n_assignments = 0
        for _, row in coded_df.iterrows():
            for code in codebook_obj.codes:
                if row.get(f"code_{code.name}") == 1:
                    session.add(CodeAssignment(
                        org_id=org_id, response_id=int(row["response_id"]), run_id=run.id,
                        code_id=code_id_by_name[code.name], confidence=float(row.get(f"conf_{code.name}", 0.0) or 0.0),
                    ))
                    n_assignments += 1

        totals = {"calls": len(usage_log), "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for u in usage_log:
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                totals[key] += u.get(key) or 0

        run.token_usage = totals
        run.status = CodingRunStatus.APPLIED
        session.commit()

        push_progress(redis_client, job_id, "done", max(1, len(coded_df)), max(1, len(coded_df)))
        return {"responses_coded": len(coded_df), "assignments": n_assignments}
    finally:
        session.close()

"""RQ jobs: propose a split or merge as a new child CodingRun.

Both reuse codeframe.refine's pure split_code()/merge_codes() against the
parent run's reconstructed coded dataframe (app/jobs/refine_common.py). The
full resulting (df, codebook) is computed once, here, at propose time --
inherited/unaffected codes are marked "accepted" (carried over, already
reviewed once), only the new split/merged code(s) are "proposed" and need
review. The per-response result is flattened into config_json["staged_assignments"]
so apply-time (app/jobs/apply.py) only has to filter it by whatever is still
"accepted" after review, not recompute anything.
"""

from __future__ import annotations

from typing import Optional

from rq import get_current_job

from app.db.base import SessionLocal
from app.db.scoped import scoped_query
from app.jobs.progress import push_progress
from app.jobs.queue import get_redis_client
from app.jobs.refine_common import build_coded_dataframe, build_llm_client, stage_assignments_from_dataframe
from app.models import CodingRun, CodingRunStatus
from codeframe.codebook import auto_code_id_for_new_code
from codeframe.refine import merge_codes, split_code


def _finish_child_run(session, run: CodingRun, updated_codebook, staged: list[dict], new_code_names: set[str], usage_log: list[dict]) -> None:
    codes_out = []
    for code in updated_codebook.codes:
        if not code.code_id:
            code.code_id = auto_code_id_for_new_code(updated_codebook, code.name)
        d = code.to_dict()
        d["status"] = "proposed" if code.name in new_code_names else "accepted"
        codes_out.append(d)

    run.codebook_json = {**updated_codebook.to_dict(), "codes": codes_out}
    cfg = dict(run.config_json)
    cfg["staged_assignments"] = staged
    run.config_json = cfg
    totals = {"calls": len(usage_log), "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for u in usage_log:
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            totals[key] += u.get(key) or 0
    run.token_usage = totals
    run.status = CodingRunStatus.DRAFT
    session.commit()


def run_propose_split_job(run_id: int, org_id: int, job_id: Optional[str] = None) -> dict:
    job = get_current_job()
    job_id = job_id or (job.id if job else "sync")
    redis_client = get_redis_client()

    session = SessionLocal()
    try:
        run = session.scalars(scoped_query(session, CodingRun, org_id).where(CodingRun.id == run_id)).one_or_none()
        if run is None:
            raise ValueError(f"CodingRun {run_id} not found for org {org_id}")
        cfg = run.config_json
        parent = session.scalars(scoped_query(session, CodingRun, org_id).where(CodingRun.id == cfg["parent_run_id"])).one_or_none()
        if parent is None:
            raise ValueError(f"Parent CodingRun {cfg['parent_run_id']} not found for org {org_id}")

        push_progress(redis_client, job_id, "loading_parent", 0, 3)
        df, parent_codebook, project_cfg, coding_cfg = build_coded_dataframe(session, org_id, parent)
        client = build_llm_client(project_cfg)

        push_progress(redis_client, job_id, "splitting", 1, 3)
        parent_code_name = next(c.name for c in parent_codebook.codes if c.code_id == cfg["parent_code_id"])
        before_names = {c.name for c in parent_codebook.codes}
        usage_log: list[dict] = []

        new_df, updated_codebook = split_code(
            df, parent_codebook, client, parent_code_name, project_cfg, coding_cfg,
            subcodes=cfg.get("subcodes") or None,
            subcode_definitions=cfg.get("subcode_definitions") or None,
            n_subcodes_proposed=cfg.get("n_proposed") or 3,
            enrich_subcodes=cfg.get("enrich_subcodes", True),
            preserve_parent=cfg.get("preserve_parent", False),
            usage_log=usage_log,
        )
        new_names = {c.name for c in updated_codebook.codes} - before_names

        push_progress(redis_client, job_id, "staging", 2, 3)
        staged = stage_assignments_from_dataframe(new_df, updated_codebook)
        _finish_child_run(session, run, updated_codebook, staged, new_names, usage_log)

        push_progress(redis_client, job_id, "done", 3, 3)
        return {"new_codes": sorted(new_names)}
    finally:
        session.close()


def run_propose_merge_job(run_id: int, org_id: int, job_id: Optional[str] = None) -> dict:
    job = get_current_job()
    job_id = job_id or (job.id if job else "sync")
    redis_client = get_redis_client()

    session = SessionLocal()
    try:
        run = session.scalars(scoped_query(session, CodingRun, org_id).where(CodingRun.id == run_id)).one_or_none()
        if run is None:
            raise ValueError(f"CodingRun {run_id} not found for org {org_id}")
        cfg = run.config_json
        parent = session.scalars(scoped_query(session, CodingRun, org_id).where(CodingRun.id == cfg["parent_run_id"])).one_or_none()
        if parent is None:
            raise ValueError(f"Parent CodingRun {cfg['parent_run_id']} not found for org {org_id}")

        push_progress(redis_client, job_id, "loading_parent", 0, 3)
        df, parent_codebook, project_cfg, coding_cfg = build_coded_dataframe(session, org_id, parent)
        client = build_llm_client(project_cfg)

        push_progress(redis_client, job_id, "merging", 1, 3)
        code_id_to_name = {c.code_id: c.name for c in parent_codebook.codes}
        codes_to_merge = [code_id_to_name[cid] for cid in cfg["code_ids"]]
        before_names = {c.name for c in parent_codebook.codes}
        usage_log: list[dict] = []

        new_df, updated_codebook = merge_codes(
            df, parent_codebook, client, codes_to_merge, project_cfg, coding_cfg,
            merged_name=cfg.get("merged_name") or "",
            merged_code_id=cfg.get("merged_code_id") or "",
            merged_definition=cfg.get("merged_definition") or "",
            enrich_merged=cfg.get("enrich_merged", True),
            usage_log=usage_log,
        )
        new_names = {c.name for c in updated_codebook.codes} - (before_names - set(codes_to_merge))

        push_progress(redis_client, job_id, "staging", 2, 3)
        staged = stage_assignments_from_dataframe(new_df, updated_codebook)
        _finish_child_run(session, run, updated_codebook, staged, new_names, usage_log)

        push_progress(redis_client, job_id, "done", 3, 3)
        return {"merged_into": sorted(new_names)}
    finally:
        session.close()

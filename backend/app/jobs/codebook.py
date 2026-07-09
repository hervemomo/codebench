"""RQ job: create a coding run's codebook.

`kind="ai"`: embed -> discover_themes -> generate_codebook (notebook S2).
`kind="import"`: parse a user-supplied codebook via load_user_codebook,
with optional AI enrichment of blank definitions (notebook S3).

Either way, every code is assigned a stable `code_id` and a review
`status: "proposed"` before being saved to `CodingRun.codebook_json` — the
human-in-the-loop review gate (app/routers/coding.py) takes it from there.
"""

from __future__ import annotations

import base64
import tempfile
from typing import Any, Optional

from rq import get_current_job

from app.config import get_settings
from app.db.base import SessionLocal
from app.db.scoped import scoped_query
from app.jobs.progress import push_progress
from app.jobs.queue import get_redis_client
from app.models import CodingRun, CodingRunStatus, Response
from codeframe import clustering
from codeframe.codebook import Codebook, auto_code_id_for_new_code, enrich_with_ai, generate_codebook, load_user_codebook
from codeframe.config import ClusterConfig, CodingConfig, ProjectConfig

_TOTAL_STAGES = 4


def _build_llm_client(project_cfg: ProjectConfig):
    if get_settings().fake_llm:
        from tests.fixtures.fake_openai import FakeOpenAI

        return FakeOpenAI()

    from openai import OpenAI

    return OpenAI(api_key=get_settings().require_openai_api_key(), timeout=project_cfg.openai_timeout_seconds)


def _load_codebook_from_source(source: Any) -> Codebook:
    """Materialize a Codebook from a `codebook_source` request payload.

    Accepted shapes:
    - a JSON list (of names or {"name", "definition", ...} dicts)
    - {"rows": [...]} -- same as a bare list
    - {"format": "xlsx"|"csv"|"json"|"txt", "content_base64": "...",
       "name_column"?, "id_column"?, "definition_column"?, "sheet"?}
    """
    if isinstance(source, list):
        return load_user_codebook(source)
    if isinstance(source, dict):
        if "rows" in source:
            return load_user_codebook(source["rows"])
        fmt = source.get("format")
        suffix = {"xlsx": ".xlsx", "xls": ".xls", "csv": ".csv", "json": ".json", "txt": ".txt"}.get(fmt)
        if suffix is None:
            raise ValueError(f"Unsupported codebook import format: {fmt!r}")
        content = base64.b64decode(source["content_base64"])
        with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
            tmp.write(content)
            tmp.flush()
            return load_user_codebook(
                tmp.name,
                name_column=source.get("name_column"),
                id_column=source.get("id_column"),
                definition_column=source.get("definition_column"),
                sheet_name=source.get("sheet", 0),
            )
    raise ValueError("codebook_source must be a list or a dict.")


def run_create_codebook_job(run_id: int, org_id: int, job_id: Optional[str] = None) -> dict:
    job = get_current_job()
    job_id = job_id or (job.id if job else "sync")
    redis_client = get_redis_client()

    session = SessionLocal()
    try:
        run = session.scalars(scoped_query(session, CodingRun, org_id).where(CodingRun.id == run_id)).one_or_none()
        if run is None:
            raise ValueError(f"CodingRun {run_id} not found for org {org_id}")
        question = run.question
        project = question.project
        cfg = run.config_json

        project_cfg = ProjectConfig(
            survey_context=project.context,
            source_language_code=project.source_lang,
            target_language_code=project.target_lang,
            codebook_language_code=project.codebook_lang,
        )
        coding_cfg = CodingConfig()
        client = _build_llm_client(project_cfg)

        push_progress(redis_client, job_id, "starting", 0, _TOTAL_STAGES)

        if cfg["kind"] == "ai":
            responses = session.scalars(
                scoped_query(session, Response, org_id).where(
                    Response.dataset_id == cfg["dataset_id"], Response.is_valid.is_(True)
                )
            ).all()
            texts = [r.translated_text for r in responses]

            push_progress(redis_client, job_id, "embedding", 1, _TOTAL_STAGES)
            embeddings = clustering.embed(texts, project_cfg, client)

            push_progress(redis_client, job_id, "clustering", 2, _TOTAL_STAGES)
            cluster_cfg = ClusterConfig(**(cfg.get("cluster_overrides") or {}))
            cluster_result = clustering.discover_themes(embeddings, texts, cluster_cfg)

            push_progress(redis_client, job_id, "generating_codebook", 3, _TOTAL_STAGES)
            target_codes = cfg.get("target_codes") or len(cluster_result.representatives)
            codebook_obj = generate_codebook(
                client, cluster_result.representatives, project_cfg, coding_cfg, target_codes=target_codes
            )
        else:
            push_progress(redis_client, job_id, "loading_codebook", 1, _TOTAL_STAGES)
            codebook_obj = _load_codebook_from_source(cfg["codebook_source"])

            if cfg.get("enrich"):
                push_progress(redis_client, job_id, "enriching", 2, _TOTAL_STAGES)
                codebook_obj = enrich_with_ai(client, codebook_obj, project_cfg, coding_cfg, fill_missing_with_fallback=True)

            push_progress(redis_client, job_id, "finalizing_import", 3, _TOTAL_STAGES)

        codes_out = []
        for code in codebook_obj.codes:
            if not code.code_id:
                code.code_id = auto_code_id_for_new_code(codebook_obj, code.name)
            d = code.to_dict()
            d["status"] = "proposed"
            codes_out.append(d)

        run.codebook_json = {**codebook_obj.to_dict(), "codes": codes_out}
        run.status = CodingRunStatus.DRAFT
        session.commit()

        push_progress(redis_client, job_id, "done", _TOTAL_STAGES, _TOTAL_STAGES)
        return {"codes": len(codes_out)}
    finally:
        session.close()

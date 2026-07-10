"""RQ job: render one export format for an APPLIED run and write it to MinIO
as an ExportArtifact. Full notebook parity (0-F): the same 5-sheet workbook,
frequency/co-occurrence CSVs, and both chart PNGs the notebook could produce,
all downloadable through the API via a presigned URL.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import Optional

from rq import get_current_job

from app import storage
from app.db.base import SessionLocal
from app.db.scoped import scoped_query
from app.jobs.progress import push_progress
from app.jobs.queue import get_redis_client
from app.jobs.refine_common import build_coded_dataframe
from app.models import CodingRun, ExportArtifact
from codeframe import reporting

_CONTENT_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv_frequencies": "text/csv",
    "csv_coded": "text/csv",
    "png_frequencies": "image/png",
    "png_cooccurrence": "image/png",
}


def _render(format: str, df, codebook, project_cfg, tmp_path: Path) -> Path:
    if format == "xlsx":
        return Path(reporting.export_workbook(df, codebook, tmp_path / "report.xlsx", text_column=project_cfg.text_column))

    if format == "csv_frequencies":
        path = tmp_path / "frequencies.csv"
        reporting.frequency_table(df, codebook).to_csv(path, index=False)
        return path

    if format == "csv_coded":
        base_cols = [c for c in ["response_id", "codes", "code_ids", "has_multi_label", "num_codes", project_cfg.text_column] if c in df.columns]
        data_cols = base_cols + [c for c in df.columns if c.startswith("code_")]
        path = tmp_path / "coded.csv"
        df[data_cols].to_csv(path, index=False)
        return path

    if format in ("png_frequencies", "png_cooccurrence"):
        charts = reporting.export_charts(df, codebook, tmp_path, file_stem="export")
        key = "frequency_chart" if format == "png_frequencies" else "cooccurrence_chart"
        chart_path = charts.get(key)
        if not chart_path:
            raise ValueError(f"No data to chart for {format} (empty codebook or no assignments).")
        return Path(chart_path)

    raise ValueError(f"Unsupported export format: {format!r}")


def run_export_job(run_id: int, org_id: int, format: str, job_id: Optional[str] = None) -> dict:
    job = get_current_job()
    job_id = job_id or (job.id if job else "sync")
    redis_client = get_redis_client()

    session = SessionLocal()
    try:
        run = session.scalars(scoped_query(session, CodingRun, org_id).where(CodingRun.id == run_id)).one_or_none()
        if run is None:
            raise ValueError(f"CodingRun {run_id} not found for org {org_id}")

        push_progress(redis_client, job_id, "building", 0, 2)
        df, codebook, project_cfg, _coding_cfg = build_coded_dataframe(session, org_id, run)

        push_progress(redis_client, job_id, "rendering", 1, 2)
        with tempfile.TemporaryDirectory() as tmp:
            path = _render(format, df, codebook, project_cfg, Path(tmp))
            data = path.read_bytes()
            key = f"exports/org-{org_id}/run-{run_id}/{uuid.uuid4()}-{path.name}"
            storage.put_object(key, data, content_type=_CONTENT_TYPES[format])

        artifact = ExportArtifact(org_id=org_id, run_id=run.id, kind=format, file_key=key)
        session.add(artifact)
        session.commit()
        session.refresh(artifact)

        push_progress(redis_client, job_id, "done", 2, 2)
        return {"artifact_id": artifact.id}
    finally:
        session.close()

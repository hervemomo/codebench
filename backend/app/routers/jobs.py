"""GET /api/jobs/{id} (latest progress snapshot) and /api/jobs/{id}/stream (SSE).

Progress lives in the Redis list `progress:{job_id}` (see app/jobs/preprocess.py).
The stream replays whatever's already there, then polls for new entries —
so it works identically whether the job already finished (tests, is_async=False)
or is still running against a real worker.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.auth import CurrentUser, get_current_user
from app.jobs.preprocess import progress_key
from app.jobs.queue import get_redis_client

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_POLL_INTERVAL_SECONDS = 0.3
_MAX_POLL_ITERATIONS = 200  # ~60s safety cap so a stream can never hang forever


def _latest_progress(job_id: str) -> dict:
    redis_client = get_redis_client()
    raw = redis_client.lindex(progress_key(job_id), -1)
    if raw is None:
        return {"stage": "pending", "current": 0, "total": 0}
    return json.loads(raw)


@router.get("/{job_id}")
def get_job(job_id: str, current: CurrentUser = Depends(get_current_user)):
    redis_client = get_redis_client()
    try:
        job = Job.fetch(job_id, connection=redis_client)
        rq_status = job.get_status(refresh=True)
    except NoSuchJobError:
        rq_status = "unknown"

    progress = _latest_progress(job_id)
    return {"id": job_id, "status": rq_status, **progress}


@router.get("/{job_id}/stream")
async def stream_job(job_id: str, current: CurrentUser = Depends(get_current_user)):
    redis_client = get_redis_client()
    key = progress_key(job_id)

    async def event_generator():
        seen = 0
        for _ in range(_MAX_POLL_ITERATIONS):
            entries = redis_client.lrange(key, seen, -1)
            for raw in entries:
                data = json.loads(raw)
                yield f"data: {raw.decode() if isinstance(raw, bytes) else raw}\n\n"
                seen += 1
                if data.get("stage") == "done":
                    return
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

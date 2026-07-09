"""Shared Redis-list progress mechanism for RQ jobs.

Every job appends `{stage, current, total}` snapshots to `progress:{job_id}`;
app/routers/jobs.py replays/polls this list regardless of which job wrote it.
"""

from __future__ import annotations

import json


def progress_key(job_id: str) -> str:
    return f"progress:{job_id}"


def push_progress(redis_client, job_id: str, stage: str, current: int, total: int) -> None:
    redis_client.rpush(
        progress_key(job_id),
        json.dumps({"stage": stage, "current": current, "total": total}),
    )

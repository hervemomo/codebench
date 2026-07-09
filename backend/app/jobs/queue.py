"""RQ queue + Redis connection factories.

`rq_is_async=False` (set via the RQ_IS_ASYNC env var) makes `queue.enqueue(...)`
execute the job inline instead of pushing it to Redis — used by tests so they
never need a separate `rq worker` process running.
"""

from __future__ import annotations

import redis
from rq import Queue

from app.config import get_settings

QUEUE_NAME = "codebench"


def get_redis_client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url)


def get_queue() -> Queue:
    return Queue(QUEUE_NAME, connection=get_redis_client(), is_async=get_settings().rq_is_async)

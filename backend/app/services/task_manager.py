from __future__ import annotations

import os

_DESKTOP_MODE = os.getenv("DESKTOP_MODE", "") == "1"

if _DESKTOP_MODE:
    from app.services.task_manager_memory import (  # noqa: F401
        create_task,
        get_task,
        pop_task,
        push_task,
        update_task,
    )
else:
    import json
    import logging
    import time
    from typing import Optional

    import redis.asyncio as aioredis

    from app.config import REDIS_URL
    from app.models import TaskInfo

    logger = logging.getLogger(__name__)

    _redis: Optional[aioredis.Redis] = None

    async def get_redis() -> aioredis.Redis:
        global _redis
        if _redis is None:
            _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
        return _redis

    def _task_key(task_id: str) -> str:
        return f"task:{task_id}"

    def _queue_key() -> str:
        return "queue:downloads"

    async def create_task(task: TaskInfo) -> TaskInfo:
        r = await get_redis()
        key = _task_key(task.task_id)
        await r.set(key, task.model_dump_json())
        await r.expire(key, 7200)
        await r.lpush(_queue_key(), task.task_id)
        logger.info("Task created: %s", task.task_id)
        return task

    async def get_task(task_id: str) -> Optional[TaskInfo]:
        r = await get_redis()
        raw = await r.get(_task_key(task_id))
        if raw is None:
            return None
        return TaskInfo(**json.loads(raw))

    async def update_task(task: TaskInfo) -> None:
        r = await get_redis()
        task.updated_at = time.time()
        await r.set(_task_key(task.task_id), task.model_dump_json())
        await r.expire(_task_key(task.task_id), 7200)

    async def pop_task() -> Optional[str]:
        r = await get_redis()
        result = await r.brpop(_queue_key(), timeout=5)
        if result is None:
            return None
        return result[1]

    async def push_task(task_id: str) -> None:
        r = await get_redis()
        await r.lpush(_queue_key(), task_id)

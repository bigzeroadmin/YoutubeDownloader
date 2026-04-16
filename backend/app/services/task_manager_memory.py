"""In-memory task manager for desktop mode (replaces Redis)."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from app.models import TaskInfo

logger = logging.getLogger(__name__)

_tasks: dict[str, str] = {}
_queue: asyncio.Queue[str] = asyncio.Queue()


async def create_task(task: TaskInfo) -> TaskInfo:
    _tasks[task.task_id] = task.model_dump_json()
    await _queue.put(task.task_id)
    logger.info("Task created (memory): %s", task.task_id)
    return task


async def get_task(task_id: str) -> Optional[TaskInfo]:
    raw = _tasks.get(task_id)
    if raw is None:
        return None
    return TaskInfo(**json.loads(raw))


async def update_task(task: TaskInfo) -> None:
    task.updated_at = time.time()
    _tasks[task.task_id] = task.model_dump_json()


async def pop_task() -> Optional[str]:
    try:
        return await asyncio.wait_for(_queue.get(), timeout=5.0)
    except asyncio.TimeoutError:
        return None


async def push_task(task_id: str) -> None:
    await _queue.put(task_id)

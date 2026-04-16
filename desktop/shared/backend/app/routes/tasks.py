from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.task_manager import get_task

router = APIRouter()


@router.get("/tasks/{task_id}")
async def task_status(task_id: str):
    task = await get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.model_dump(exclude={"url"})

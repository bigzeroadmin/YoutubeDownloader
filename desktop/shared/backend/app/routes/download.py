from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models import DownloadRequest, TaskInfo
from app.services.task_manager import create_task
from app.services.ytdlp_service import validate_url

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/download")
async def download(req: DownloadRequest):
    try:
        validate_url(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    task = TaskInfo(
        url=req.url,
        format_id=req.format_id,
        audio_only=req.audio_only,
        convert_mp3=req.convert_mp3,
        has_audio=req.has_audio,
        expected_filesize=req.expected_filesize,
    )
    await create_task(task)
    return {"task_id": task.task_id, "status": task.status.value}

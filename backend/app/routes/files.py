from __future__ import annotations

import mimetypes
import re
import stat
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from app.config import DOWNLOAD_DIR
from app.services.task_manager import get_task

router = APIRouter()

_RANGE_RE = re.compile(r"bytes=(\d+)-(\d*)")
_CHUNK_SIZE = 256 * 1024  # 256 KB


def _resolve_file(task_id: str, filename: str) -> Path:
    file_path = DOWNLOAD_DIR / task_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=410, detail="File expired or deleted")
    try:
        file_path.resolve().relative_to(DOWNLOAD_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    return file_path


def _content_type(filename: str) -> str:
    mt, _ = mimetypes.guess_type(filename)
    return mt or "application/octet-stream"


@router.head("/files/{task_id}")
@router.get("/files/{task_id}")
async def get_file(task_id: str, request: Request):
    task = await get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status.value != "success":
        raise HTTPException(status_code=400, detail=f"Task status: {task.status.value}")
    if not task.filename:
        raise HTTPException(status_code=500, detail="No filename recorded")

    file_path = _resolve_file(task_id, task.filename)
    file_size = file_path.stat().st_size
    content_type = _content_type(task.filename)
    encoded_name = quote(task.filename)
    disposition = f'attachment; filename="{encoded_name}"; filename*=UTF-8\'\'{encoded_name}'

    range_header = request.headers.get("range")
    if range_header:
        m = _RANGE_RE.match(range_header)
        if not m:
            raise HTTPException(status_code=416, detail="Invalid Range header")

        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else file_size - 1
        end = min(end, file_size - 1)

        if start > end or start >= file_size:
            return Response(
                status_code=416,
                headers={"Content-Range": f"bytes */{file_size}"},
            )

        length = end - start + 1

        def _range_iter():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(_CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            _range_iter(),
            status_code=206,
            media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(length),
                "Content-Disposition": disposition,
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache",
            },
        )

    def _full_iter():
        with open(file_path, "rb") as f:
            while chunk := f.read(_CHUNK_SIZE):
                yield chunk

    return StreamingResponse(
        _full_iter(),
        status_code=200,
        media_type=content_type,
        headers={
            "Content-Length": str(file_size),
            "Content-Disposition": disposition,
            "Accept-Ranges": "bytes",
            "Cache-Control": "no-cache",
        },
    )

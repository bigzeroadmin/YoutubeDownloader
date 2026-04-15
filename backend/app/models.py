from __future__ import annotations

import enum
import time
import uuid
from typing import Optional

from pydantic import BaseModel, Field


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class FormatInfo(BaseModel):
    format_id: str
    ext: str
    resolution: Optional[str] = None
    filesize: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    abr: Optional[float] = None
    fps: Optional[float] = None
    note: Optional[str] = None


class ResolveRequest(BaseModel):
    url: str


class ResolveResponse(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    formats: list[FormatInfo]


class DownloadRequest(BaseModel):
    url: str
    format_id: str
    audio_only: bool = False
    convert_mp3: bool = False


class TaskInfo(BaseModel):
    task_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    status: TaskStatus = TaskStatus.PENDING
    url: str = ""
    format_id: str = ""
    audio_only: bool = False
    convert_mp3: bool = False
    filename: Optional[str] = None
    filesize: Optional[int] = None
    error: Optional[str] = None
    progress: float = 0.0
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    retries: int = 0

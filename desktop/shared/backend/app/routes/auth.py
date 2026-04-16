from __future__ import annotations

from fastapi import APIRouter

from app.services.ytdlp_service import check_auth_status

router = APIRouter()


@router.get("/auth/status")
async def auth_status():
    return check_auth_status()

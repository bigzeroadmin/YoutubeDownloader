from __future__ import annotations

from fastapi import APIRouter

from app.config import COOKIE_MAX_AGE_SECONDS
from app.services.ytdlp_service import check_auth_status, get_cookie_age_seconds

router = APIRouter()


@router.get("/cookies/status")
async def cookies_status():
    base = check_auth_status()
    age = get_cookie_age_seconds()
    base["age_seconds"] = int(age) if age is not None else None
    base["max_age_seconds"] = COOKIE_MAX_AGE_SECONDS
    base["is_fresh"] = age is not None and age <= COOKIE_MAX_AGE_SECONDS
    return base

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter

from app.config import (
    COOKIE_MAX_AGE_SECONDS,
    COOKIES_FILE,
    COOKIES_FROM_BROWSER,
    DESKTOP_MODE,
)
from app.services.ytdlp_service import check_auth_status, get_cookie_age_seconds

logger = logging.getLogger(__name__)
router = APIRouter()

_refresh_executor = ThreadPoolExecutor(max_workers=1)


@router.get("/cookies/status")
async def cookies_status():
    base = check_auth_status()
    age = get_cookie_age_seconds()
    base["age_seconds"] = int(age) if age is not None else None
    base["max_age_seconds"] = COOKIE_MAX_AGE_SECONDS
    base["is_fresh"] = age is not None and age <= COOKIE_MAX_AGE_SECONDS
    base["browser"] = COOKIES_FROM_BROWSER or None
    base["desktop_mode"] = DESKTOP_MODE
    return base


def _do_refresh_cookies() -> dict:
    """Synchronous: use yt-dlp to extract cookies from browser to file."""
    import yt_dlp

    if not COOKIES_FROM_BROWSER:
        return {"ok": False, "error": "No browser configured for cookie extraction"}
    if not COOKIES_FILE:
        return {"ok": False, "error": "No cookies file path configured"}

    cookie_path = Path(COOKIES_FILE)
    cookie_path.parent.mkdir(parents=True, exist_ok=True)

    # Write empty Netscape header to start fresh
    cookie_path.write_text("# Netscape HTTP Cookie File\n")

    opts = {
        "cookiesfrombrowser": (COOKIES_FROM_BROWSER,),
        "cookiefile": str(cookie_path),
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info("https://www.youtube.com/watch?v=jNQXAC9IVRw", download=False)
    except Exception as exc:
        # Even if extraction fails, cookies may have been written
        logger.warning("Cookie refresh extraction had an error: %s", exc)

    # Count cookies written
    count = 0
    if cookie_path.is_file():
        for line in cookie_path.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                count += 1

    if count > 0:
        logger.info("Cookie refresh OK: %d cookies from %s", count, COOKIES_FROM_BROWSER)
        return {"ok": True, "cookie_count": count, "browser": COOKIES_FROM_BROWSER}
    else:
        return {"ok": False, "error": f"No cookies extracted from {COOKIES_FROM_BROWSER}", "cookie_count": 0}


@router.post("/cookies/refresh")
async def refresh_cookies():
    """Extract cookies from the user's browser and write to cookies file."""
    if not DESKTOP_MODE:
        return {"ok": False, "error": "Cookie refresh is only available in desktop mode"}

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(_refresh_executor, _do_refresh_cookies)
    return result

from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from app.config import (
    ALLOWED_HOSTS,
    AUTH_MODE,
    COOKIE_MAX_AGE_SECONDS,
    COOKIES_FILE,
    COOKIES_FROM_BROWSER,
    RESOLVE_TIMEOUT_SECONDS,
    YTDLP_CACHE_DIR,
)
from app.models import FormatInfo, ResolveResponse

logger = logging.getLogger(__name__)

_URL_RE = re.compile(
    r"^https?://(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/",
)

_COOKIE_ERROR_RE = re.compile(
    r"(HTTP Error 403|Sign in to confirm|cookies?\s*(are\s*)?expired|"
    r"login required|session\s*expired|consent\s*required|"
    r"This request was detected as a bot)",
    re.IGNORECASE,
)


def get_cookie_age_seconds() -> float | None:
    """Return age of cookies.txt in seconds, or None if file missing."""
    if not COOKIES_FILE:
        return None
    p = Path(COOKIES_FILE)
    if not p.is_file():
        return None
    return time.time() - p.stat().st_mtime


def is_cookie_error(exc: Exception) -> bool:
    """Return True if the exception looks like a cookie/auth problem."""
    return bool(_COOKIE_ERROR_RE.search(str(exc)))


def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http/https URLs are allowed")
    host = parsed.hostname or ""
    if not any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS):
        raise ValueError(f"Host {host} is not allowed")
    return url


def _has_video(f: dict) -> bool:
    return bool(f.get("vcodec") and f["vcodec"] != "none")


def _has_audio(f: dict) -> bool:
    return bool(f.get("acodec") and f["acodec"] != "none")


def _base_opts() -> dict:
    """Common yt-dlp options shared by resolve and download."""
    opts: dict = {
        "js_runtimes": {"node": {}},
        "remote_components": {"ejs:github"},
        "cachedir": YTDLP_CACHE_DIR,
    }

    if AUTH_MODE == "cookies":
        if COOKIES_FILE and Path(COOKIES_FILE).is_file():
            opts["cookiefile"] = COOKIES_FILE
    elif AUTH_MODE == "browser":
        if COOKIES_FROM_BROWSER:
            opts["cookiesfrombrowser"] = (COOKIES_FROM_BROWSER,)

    return opts


def check_auth_status() -> dict:
    """Check whether cookie file exists and has content."""
    has_cookies = False
    cookie_count = 0
    if COOKIES_FILE and Path(COOKIES_FILE).is_file():
        with open(COOKIES_FILE) as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    cookie_count += 1
        has_cookies = cookie_count > 0

    return {
        "auth_mode": AUTH_MODE,
        "cookies_file": COOKIES_FILE or "(not set)",
        "cookie_count": cookie_count,
        "ready": has_cookies if AUTH_MODE == "cookies" else bool(COOKIES_FROM_BROWSER),
    }


def resolve_formats(url: str) -> ResolveResponse:
    url = validate_url(url)
    ydl_opts = {
        **_base_opts(),
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "ignore_no_formats_error": True,
        "socket_timeout": RESOLVE_TIMEOUT_SECONDS,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if info is None:
            raise RuntimeError("Failed to extract video info")
        if not info.get("formats"):
            raise RuntimeError(
                "No formats available. Cookies may be invalid or expired. "
                "Run: ./refresh_cookies.sh (or re-export manually)"
            )

    raw_formats = info.get("formats") or []
    formats: list[FormatInfo] = []
    seen: set[str] = set()

    video_only: list[dict] = []
    best_audio: dict | None = None

    for f in raw_formats:
        fid = f.get("format_id", "")
        if fid in seen:
            continue
        seen.add(fid)

        resolution = f.get("resolution") or f.get("format_note")
        if f.get("height"):
            resolution = f"{f['height']}p"

        formats.append(
            FormatInfo(
                format_id=fid,
                ext=f.get("ext", "unknown"),
                resolution=resolution,
                filesize=f.get("filesize") or f.get("filesize_approx"),
                vcodec=f.get("vcodec"),
                acodec=f.get("acodec"),
                abr=f.get("abr"),
                fps=f.get("fps"),
                note=f.get("format_note"),
            )
        )

        if _has_video(f) and not _has_audio(f):
            video_only.append(f)
        if _has_audio(f) and not _has_video(f):
            abr = f.get("abr") or 0
            if best_audio is None or abr > (best_audio.get("abr") or 0):
                best_audio = f

    # Synthesise merged "video+audio" options for DASH-only resolutions
    if best_audio and video_only:
        ba_id = best_audio["format_id"]
        for vf in video_only:
            merged_id = f"{vf['format_id']}+{ba_id}"
            if merged_id in seen:
                continue
            seen.add(merged_id)
            height = vf.get("height")
            resolution = f"{height}p" if height else vf.get("format_note", "?")
            vsize = vf.get("filesize") or vf.get("filesize_approx") or 0
            asize = best_audio.get("filesize") or best_audio.get("filesize_approx") or 0
            merged_size = (vsize + asize) if (vsize and asize) else None
            formats.append(
                FormatInfo(
                    format_id=merged_id,
                    ext="mp4",
                    resolution=resolution,
                    filesize=merged_size,
                    vcodec=vf.get("vcodec"),
                    acodec=best_audio.get("acodec"),
                    abr=best_audio.get("abr"),
                    fps=vf.get("fps"),
                    note=f"{resolution} merged",
                )
            )

    return ResolveResponse(
        title=info.get("title", "Untitled"),
        thumbnail=info.get("thumbnail"),
        duration=info.get("duration"),
        formats=formats,
    )

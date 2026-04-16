"""Wait for the cookie file to be refreshed by an external process (cron / manual).

The worker runs inside Docker and cannot access the host browser.  When it
detects a cookie error it calls `wait_for_cookie_refresh()`, which polls the
bind-mounted cookies.txt for an mtime change.  The actual refresh is done on
the host side by cron running `refresh_cookies.sh`.

No extra watchdog process is needed — just a cron job on the host:
    */30 * * * * /path/to/YoutubeDownload/refresh_cookies.sh edge >> /tmp/cookie_refresh.log 2>&1
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.config import COOKIE_REFRESH_WAIT_SECONDS, COOKIES_FILE

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 5  # seconds between mtime checks


async def wait_for_cookie_refresh(
    timeout: float | None = None,
) -> bool:
    """Block until cookies.txt is updated on disk, or timeout.

    Returns True if the file's mtime changed (fresh cookies available),
    False if the wait timed out.
    """
    if timeout is None:
        timeout = COOKIE_REFRESH_WAIT_SECONDS

    cookie_path = Path(COOKIES_FILE) if COOKIES_FILE else None
    if cookie_path is None or not cookie_path.is_file():
        logger.warning("No cookie file configured, cannot wait for refresh")
        return False

    old_mtime = cookie_path.stat().st_mtime
    elapsed = 0.0

    logger.info(
        "Waiting up to %ds for cookies.txt to be refreshed (mtime=%d)...",
        int(timeout), int(old_mtime),
    )

    while elapsed < timeout:
        await asyncio.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

        if not cookie_path.is_file():
            continue

        new_mtime = cookie_path.stat().st_mtime
        if new_mtime > old_mtime:
            logger.info(
                "Cookie file updated after %ds (mtime %d → %d)",
                int(elapsed), int(old_mtime), int(new_mtime),
            )
            return True

    logger.warning("Cookie refresh timed out after %ds", int(timeout))
    return False

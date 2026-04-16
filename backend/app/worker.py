"""Background worker that processes download tasks from the Redis queue."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yt_dlp

from app.config import (
    COOKIE_MAX_AGE_SECONDS,
    COOKIE_RETRY_MAX,
    DOWNLOAD_DIR,
    DOWNLOAD_TIMEOUT_SECONDS,
    LARGE_FILE_THRESHOLD_BYTES,
    LARGE_FILE_TIMEOUT_SECONDS,
    MAX_CONCURRENT_DOWNLOADS,
    WORKER_MAX_RETRIES,
    WORKER_RETRY_DELAY_SECONDS,
)
from app.models import TaskInfo, TaskStatus
from app.services.task_manager import get_redis, get_task, pop_task, update_task
from app.services.ytdlp_service import _base_opts, get_cookie_age_seconds, is_cookie_error

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("worker")

_shutdown = False
_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS)

_NON_RETRYABLE_PATTERNS = re.compile(
    r"(format.*not available|no video formats|unavailable|private video|"
    r"copyright|removed)",
    re.IGNORECASE,
)


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc)
    if _NON_RETRYABLE_PATTERNS.search(msg):
        return False
    return True


def _handle_signal(*_):
    global _shutdown
    _shutdown = True
    logger.info("Shutdown signal received")


def _compute_timeout(task: TaskInfo) -> float:
    """Return timeout in seconds; use longer timeout for large files."""
    if task.expected_filesize and task.expected_filesize > LARGE_FILE_THRESHOLD_BYTES:
        return LARGE_FILE_TIMEOUT_SECONDS
    return DOWNLOAD_TIMEOUT_SECONDS


def _progress_hook(task: TaskInfo):
    def hook(d: dict):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            if total > 0:
                task.progress = round(downloaded / total * 100, 1)
        elif d.get("status") == "finished":
            task.progress = 100.0
            task.filename = os.path.basename(d.get("filename", ""))
    return hook


def _run_ytdlp(task: TaskInfo, task_dir: Path) -> None:
    """Synchronous yt-dlp download — runs in a thread."""
    is_merged = "+" in task.format_id

    ydl_opts: dict = {
        **_base_opts(),
        "format": task.format_id,
        "outtmpl": str(task_dir / "%(title)s.%(ext)s"),
        "socket_timeout": 30,
        "progress_hooks": [_progress_hook(task)],
        "quiet": True,
        "no_warnings": True,
        # --- Resume & retry ---
        "continuedl": True,
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 3,
        "extractor_retries": 3,
        "retry_sleep_functions": {"http": lambda n: min(2 ** n, 30)},
        "noprogress": False,
    }

    if is_merged:
        ydl_opts["merge_output_format"] = "mp4"

    if task.convert_mp3:
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    elif task.audio_only:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "192",
            }
        ]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([task.url])


def _find_result_file(task_dir: Path) -> Path | None:
    """Find the completed download file, ignoring .part / .ytdl temp files."""
    for f in task_dir.iterdir():
        if f.is_file() and not f.suffix in (".part", ".ytdl"):
            return f
    return None


async def _sync_progress(task: TaskInfo, stop_event: asyncio.Event):
    """Periodically flush task.progress to Redis while downloading."""
    while not stop_event.is_set():
        await update_task(task)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass


async def _retry_delay(attempt: int) -> None:
    """Exponential backoff: base * 2^attempt, capped at 60s."""
    delay = min(WORKER_RETRY_DELAY_SECONDS * (2 ** (attempt - 1)), 60)
    logger.info("Waiting %ds before retry...", delay)
    await asyncio.sleep(delay)


async def _handle_cookie_error(task: TaskInfo, exc: Exception) -> None:
    """Handle cookie/auth errors with dedicated retry + optional refresh wait."""
    task.cookie_retries += 1
    if task.cookie_retries <= COOKIE_RETRY_MAX:
        task.status = TaskStatus.WAITING_COOKIES
        task.error = (
            f"Cookie/auth error, waiting for refresh "
            f"({task.cookie_retries}/{COOKIE_RETRY_MAX}): {exc}"
        )
        logger.warning(
            "Task %s cookie error (%d/%d): %s",
            task.task_id, task.cookie_retries, COOKIE_RETRY_MAX, exc,
        )
        await update_task(task)

        # Wait for host-side cron to refresh the cookie file
        from app.services.cookie_refresh import wait_for_cookie_refresh
        refreshed = await wait_for_cookie_refresh()

        if refreshed:
            task.status = TaskStatus.PENDING
            task.error = "Cookies refreshed, retrying..."
            logger.info("Task %s: cookies refreshed, re-queuing", task.task_id)
        else:
            task.status = TaskStatus.PENDING
            task.error = (
                f"Cookie refresh timed out, retrying with current cookies "
                f"({task.cookie_retries}/{COOKIE_RETRY_MAX})"
            )
            logger.warning("Task %s: cookie refresh timed out, retrying anyway", task.task_id)

        r = await get_redis()
        await r.lpush("queue:downloads", task.task_id)
        await asyncio.sleep(2)
    else:
        task.status = TaskStatus.FAILED
        task.error = (
            f"Cookie/auth failed after {COOKIE_RETRY_MAX} refresh attempts: {exc}. "
            "Run ./refresh_cookies.sh manually."
        )
        logger.error("Task %s cookie auth failed permanently: %s", task.task_id, exc)


async def process_task(task: TaskInfo) -> None:
    task.status = TaskStatus.RUNNING
    task.updated_at = time.time()
    await update_task(task)

    # Pre-download cookie freshness check
    cookie_age = get_cookie_age_seconds()
    if cookie_age is not None and cookie_age > COOKIE_MAX_AGE_SECONDS:
        logger.warning(
            "Task %s: cookies are %ds old (max %ds), may expire during download",
            task.task_id, int(cookie_age), COOKIE_MAX_AGE_SECONDS,
        )

    task_dir = DOWNLOAD_DIR / task.task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    stop_event = asyncio.Event()
    progress_coro = _sync_progress(task, stop_event)
    progress_task = asyncio.create_task(progress_coro)

    timeout = _compute_timeout(task)
    loop = asyncio.get_running_loop()
    try:
        await asyncio.wait_for(
            loop.run_in_executor(_executor, _run_ytdlp, task, task_dir),
            timeout=timeout,
        )

        result_file = _find_result_file(task_dir)
        if result_file is None:
            raise RuntimeError("No file was downloaded")

        task.filename = result_file.name
        task.filesize = result_file.stat().st_size
        task.status = TaskStatus.SUCCESS
        task.progress = 100.0
        logger.info("Task %s completed: %s (%s bytes)", task.task_id, task.filename, task.filesize)

    except asyncio.TimeoutError:
        task.retries += 1
        if task.retries < WORKER_MAX_RETRIES:
            task.status = TaskStatus.PENDING
            task.error = f"Timeout retry {task.retries}/{WORKER_MAX_RETRIES}"
            logger.warning("Task %s timed out, will retry (%d/%d)", task.task_id, task.retries, WORKER_MAX_RETRIES)
            r = await get_redis()
            await r.lpush("queue:downloads", task.task_id)
            await _retry_delay(task.retries)
        else:
            task.status = TaskStatus.FAILED
            task.error = f"Download timed out after {WORKER_MAX_RETRIES} attempts"
            logger.error("Task %s timed out permanently", task.task_id)

    except Exception as exc:
        if is_cookie_error(exc):
            await _handle_cookie_error(task, exc)
        else:
            retryable = _is_retryable(exc)
            task.retries += 1

            if retryable and task.retries < WORKER_MAX_RETRIES:
                task.status = TaskStatus.PENDING
                task.error = f"Retry {task.retries}/{WORKER_MAX_RETRIES}: {exc}"
                logger.warning("Task %s retry %d/%d: %s", task.task_id, task.retries, WORKER_MAX_RETRIES, exc)
                r = await get_redis()
                await r.lpush("queue:downloads", task.task_id)
                await _retry_delay(task.retries)
            else:
                task.status = TaskStatus.FAILED
                task.error = str(exc) if not retryable else f"Failed after {WORKER_MAX_RETRIES} attempts: {exc}"
                logger.error("Task %s failed (retryable=%s): %s", task.task_id, retryable, exc)

    finally:
        stop_event.set()
        await progress_task

    await update_task(task)


async def worker_loop():
    sem = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    logger.info(
        "Worker started (concurrency=%d, retries=%d)",
        MAX_CONCURRENT_DOWNLOADS,
        WORKER_MAX_RETRIES,
    )

    async def _run(task_id: str):
        async with sem:
            task = await get_task(task_id)
            if task is None:
                logger.warning("Task %s not found, skipping", task_id)
                return
            await process_task(task)

    tasks: set[asyncio.Task] = set()
    while not _shutdown:
        task_id = await pop_task()
        if task_id is None:
            continue
        t = asyncio.create_task(_run(task_id))
        tasks.add(t)
        t.add_done_callback(tasks.discard)

    if tasks:
        logger.info("Waiting for %d active tasks to finish...", len(tasks))
        await asyncio.gather(*tasks, return_exceptions=True)

    logger.info("Worker stopped")


def main():
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    main()

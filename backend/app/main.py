from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import CLEANUP_INTERVAL_SECONDS, DESKTOP_MODE, DOWNLOAD_DIR, ELECTRON_RESOURCES_PATH, FILE_TTL_SECONDS
from app.routes import auth, cookies, download, files, resolve, tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_cleanup_task = None
_worker_task = None


async def _cleanup_expired_files():
    """Periodically remove download directories older than FILE_TTL_SECONDS."""
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        now = time.time()
        try:
            for task_dir in DOWNLOAD_DIR.iterdir():
                if not task_dir.is_dir():
                    continue
                age = now - task_dir.stat().st_mtime
                if age > FILE_TTL_SECONDS:
                    import shutil
                    shutil.rmtree(task_dir, ignore_errors=True)
                    logger.info("Cleaned up expired dir: %s", task_dir.name)
        except Exception:
            logger.exception("Cleanup error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cleanup_task, _worker_task
    _cleanup_task = asyncio.create_task(_cleanup_expired_files())
    logger.info("App started – cleanup task scheduled every %ds", CLEANUP_INTERVAL_SECONDS)

    if DESKTOP_MODE:
        from app.worker import worker_loop
        _worker_task = asyncio.create_task(worker_loop())
        logger.info("Desktop mode – embedded worker started")

        # Auto-refresh cookies from browser on startup
        from app.routes.cookies import _do_refresh_cookies
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(None, _do_refresh_cookies)
            if result.get("ok"):
                logger.info("Startup cookie refresh OK: %d cookies from %s",
                            result.get("cookie_count", 0), result.get("browser", "?"))
            else:
                logger.warning("Startup cookie refresh failed: %s", result.get("error", "unknown"))
        except Exception:
            logger.exception("Startup cookie refresh error")

    yield

    if _worker_task is not None:
        from app import worker as _worker_mod
        _worker_mod._shutdown = True
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Embedded worker stopped")

    _cleanup_task.cancel()
    logger.info("App shutting down")


app = FastAPI(
    title="YouTube Downloader API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(cookies.router, prefix="/api", tags=["cookies"])
app.include_router(resolve.router, prefix="/api", tags=["resolve"])
app.include_router(download.router, prefix="/api", tags=["download"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(files.router, prefix="/api", tags=["files"])

# Resolve frontend directory: Electron bundle → fallback to project layout
_frontend_candidates = []
if ELECTRON_RESOURCES_PATH:
    _frontend_candidates.append(Path(ELECTRON_RESOURCES_PATH) / "frontend")
_frontend_candidates.append(Path(__file__).resolve().parent.parent.parent / "frontend")

FRONTEND_DIR = None
for _candidate in _frontend_candidates:
    if _candidate.exists():
        FRONTEND_DIR = _candidate
        break

if FRONTEND_DIR is not None:
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

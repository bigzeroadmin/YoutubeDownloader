from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import CLEANUP_INTERVAL_SECONDS, DOWNLOAD_DIR, FILE_TTL_SECONDS
from app.routes import auth, cookies, download, files, resolve, tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_cleanup_task = None


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
    global _cleanup_task
    _cleanup_task = asyncio.create_task(_cleanup_expired_files())
    logger.info("App started – cleanup task scheduled every %ds", CLEANUP_INTERVAL_SECONDS)
    yield
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

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

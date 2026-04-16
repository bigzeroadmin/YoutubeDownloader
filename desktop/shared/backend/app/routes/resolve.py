from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models import ResolveRequest, ResolveResponse
from app.services.ytdlp_service import resolve_formats

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/resolve", response_model=ResolveResponse)
async def resolve(req: ResolveRequest):
    try:
        return resolve_formats(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Resolve failed for %s", req.url)
        raise HTTPException(status_code=500, detail=f"Resolve failed: {exc}")

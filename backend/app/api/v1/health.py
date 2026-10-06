"""Health and readiness endpoints."""

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.database.session import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", summary="Liveness and readiness probe")
async def health(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    settings = request.app.state.settings

    # 1. Check database connection
    db_status = "down"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "up"
    except Exception as exc:
        logger.debug("Health check: database unreachable: %s", exc)

    # 2. Check Redis connection
    redis_status = "down"
    try:
        session_store = request.app.state.session_store
        if hasattr(session_store, "_redis"):
            await session_store._redis.ping()
            redis_status = "up"
        else:
            redis_status = "up"  # in-memory fallback is treated as up
    except Exception as exc:
        logger.debug("Health check: session store unreachable: %s", exc)

    overall_status = "ok" if db_status == "up" and redis_status == "up" else "degraded"

    return {
        "status": overall_status,
        "service": settings.app_name,
        "environment": settings.app_env,
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": getattr(request.state, "request_id", None),
        "database": db_status,
        "redis": redis_status,
    }

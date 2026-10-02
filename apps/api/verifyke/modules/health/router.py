"""Health, readiness and version probes.

* ``/health``  - liveness only: the process is up and serving. No dependencies
                 are touched, so a database outage does not cause a restart loop.
* ``/ready``   - readiness: verifies PostgreSQL, Redis and object storage. Returns
                 503 with a per-dependency breakdown when anything is unhealthy.
* ``/version`` - build/version metadata, safe for public consumption.

These endpoints are excluded from rate limiting and never expose configuration
values, credentials or topology beyond dependency names.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from verifyke import __version__
from verifyke.core.config import Settings, get_settings
from verifyke.core.db import check_database, get_session
from verifyke.core.logging import get_logger
from verifyke.core.redis_client import redis_info

logger = get_logger(__name__)

router = APIRouter(tags=["system"])

_STARTED_MONOTONIC = time.monotonic()


@router.get(
    "/health",
    summary="Liveness probe",
    description="Process liveness; no dependencies are checked.",
)
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "verifyke-api",
        "version": __version__,
        "uptime_seconds": round(time.monotonic() - _STARTED_MONOTONIC, 2),
    }


@router.get("/version", summary="Service version")
async def version(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    return {
        "service": "verifyke-api",
        "version": __version__,
        "environment": settings.app_env,
    }


@router.get("/ready", summary="Readiness probe")
async def ready(
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Check every hard dependency; 503 when any of them is unusable."""
    dependencies: dict[str, Any] = {}

    try:
        await check_database(session)
        dependencies["database"] = {"status": "ok"}
    except Exception as exc:
        logger.error("readiness_database_failed", error=type(exc).__name__)
        dependencies["database"] = {"status": "error", "error": type(exc).__name__}

    redis_state = await redis_info()
    dependencies["redis"] = redis_state
    if not redis_state.get("available"):
        # Rate limiting and background verification depend on Redis.
        dependencies["redis"]["status"] = "error"

    healthy = all(
        state.get("status", "ok" if state.get("available") else "error") == "ok"
        for state in dependencies.values()
    )
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "dependencies": dependencies}

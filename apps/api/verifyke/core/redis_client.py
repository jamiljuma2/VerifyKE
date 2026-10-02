"""Redis client management (cache, rate limiting, Celery broker).

The client is created lazily and shared process-wide. Redis is a *soft*
dependency for most request paths (cache, rate limiting degrade gracefully and
log a warning), but a *hard* dependency for the readiness probe - an instance
that cannot rate-limit should be taken out of the load balancer rather than fail
open silently in production.
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as redis
from redis.exceptions import RedisError

from verifyke.core.config import Settings, get_settings
from verifyke.core.logging import get_logger

logger = get_logger(__name__)

_client: redis.Redis | None = None


def get_redis_client(settings: Settings | None = None) -> redis.Redis:
    """Return the shared async Redis client (no connection is opened yet)."""
    global _client
    if _client is None:
        settings = settings or get_settings()
        _client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
            max_connections=50,
        )
    return _client


async def get_redis() -> redis.Redis:
    """FastAPI dependency returning the Redis client."""
    return get_redis_client()


async def redis_available() -> bool:
    """Return ``True`` when Redis answers a PING within the socket timeout."""
    try:
        await get_redis_client().ping()
    except (RedisError, OSError) as exc:
        logger.warning("redis_unavailable", error=str(exc))
        return False
    return True


async def close_redis() -> None:
    """Close the client on application shutdown."""
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        except (RedisError, OSError) as exc:  # pragma: no cover - shutdown path
            logger.warning("redis_close_failed", error=str(exc))
    _client = None


def reset_client_state() -> None:
    """Forget the cached client without awaiting a close.

    Needed by the test-suite (each test gets its own event loop, while the client
    is a process-level singleton) and after a ``fork`` in a preload-based server.
    """
    global _client
    _client = None


async def redis_info() -> dict[str, Any]:
    """Subset of INFO used by the readiness endpoint."""
    try:
        info = await get_redis_client().info(section="server")
    except (RedisError, OSError) as exc:
        return {"available": False, "error": type(exc).__name__}
    return {
        "available": True,
        "version": info.get("redis_version"),
    }

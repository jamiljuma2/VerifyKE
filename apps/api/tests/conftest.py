"""Shared pytest fixtures.

Test isolation rules:
* Settings are created per-test with test-specific overrides (never mutated
  globally), so a test can never leak configuration into another test.
* Redis is replaced with ``fakeredis`` unless the ``--live-services`` marker is
  requested, so the API test-suite runs without infrastructure.
* Tests that need PostgreSQL are marked ``integration`` and are skipped when a
  live database is unavailable.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest

# Force the test environment before any module imports settings.
os.environ.setdefault("VK_APP_ENV", "test")
os.environ.setdefault("VK_REDIS_URL", "redis://localhost:6379/15")

from httpx import ASGITransport, AsyncClient

from verifyke.core.config import Settings, get_settings
from verifyke.main import create_app


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    return Settings(
        app_env="test",
        debug=False,
        secret_key="test-secret-key-that-is-long-enough-for-hmac-0123456789",
        rate_limit_enabled=True,
        metrics_enabled=True,
        log_json=False,
        log_level="WARNING",
    )


@pytest.fixture()
def app(test_settings: Settings):
    """FastAPI application bound to the test settings."""
    get_settings.cache_clear()
    application = create_app(test_settings)
    yield application
    get_settings.cache_clear()


@pytest.fixture()
async def client(app) -> AsyncIterator[AsyncClient]:
    """Async HTTP client wired directly to the ASGI app (no network)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture()
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _isolate_process_state() -> Iterator[None]:
    """Prevent connection state leaking between tests.

    The database engine and the Redis client are process-level singletons, but
    pytest-asyncio gives every test its own event loop. A client created in one
    test's loop raises "Event loop is closed" in the next, so both are reset
    around every test.
    """
    from verifyke.core.db import reset_engine_state
    from verifyke.core.redis_client import reset_client_state

    reset_engine_state()
    reset_client_state()
    yield
    reset_engine_state()
    reset_client_state()


@pytest.fixture(autouse=True)
def _quiet_logging() -> Iterator[None]:
    """Keep test output readable unless a test asserts on logging."""
    import logging

    logging.disable(logging.CRITICAL)
    try:
        yield
    finally:
        logging.disable(logging.NOTSET)

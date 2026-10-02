"""Rate-limit dependency wiring and logging configuration."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import Depends
from httpx import AsyncClient

# The tests directory is not a package: pytest inserts it on sys.path, so the
# shared FakeRedis lives in test_rate_limit and is imported directly.
from test_rate_limit import FakeRedis

from verifyke.core import rate_limit as rl
from verifyke.core.config import Settings
from verifyke.core.logging import configure_logging


async def test_endpoint_dependency_enforces_its_own_limit(
    app: Any, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A route with a named limit returns 429 with the documented envelope."""
    # One shared fake: the counter must survive across requests.
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis_client", lambda *_: fake)
    monkeypatch.setattr(
        rl, "get_settings", lambda: Settings(app_env="test", rate_limit_default="2/1m")
    )

    dependency = rl.rate_limit_dependency("probe", "rate_limit_default")

    @app.get("/_probe/limited", include_in_schema=False)
    async def limited(result: Any = Depends(dependency)) -> dict[str, Any]:
        return {"ok": True, "remaining": result.remaining}

    first = await client.get("/_probe/limited")
    second = await client.get("/_probe/limited")
    third = await client.get("/_probe/limited")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.headers["retry-after"] == "60"
    error = third.json()["error"]
    assert error["code"] == "RATE_LIMITED"
    assert "request_id" in error


async def test_configure_logging_is_idempotent_in_both_formats() -> None:
    """Both renderers must configure cleanly and repeatedly (startup + reload)."""
    for json_logs in (True, False):
        settings = Settings(app_env="test", log_json=json_logs, log_level="INFO")
        configure_logging(settings)
        configure_logging(settings)

    from verifyke.core.logging import get_logger

    logger = get_logger("verifyke.tests.logging")
    # Emitting must not raise with either renderer configured.
    logger.info("test_event", detail="ok")

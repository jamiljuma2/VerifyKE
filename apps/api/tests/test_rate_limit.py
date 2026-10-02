"""Rate limiter behaviour, including the deliberate fail-open policy."""

from __future__ import annotations

import pytest
from redis.exceptions import RedisError

from verifyke.core import rate_limit as rl
from verifyke.core.config import Settings


class FakeRedis:
    """Minimal stand-in for the atomic INCR/PEXPIRE script."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}

    async def eval(self, _script: str, _numkeys: int, key: str, window_ms: int):
        self.counters[key] = self.counters.get(key, 0) + 1
        return [self.counters[key], window_ms]


class BrokenRedis:
    async def eval(self, *_args, **_kwargs):
        raise RedisError("connection refused")


@pytest.fixture()
def settings() -> Settings:
    return Settings(app_env="test", rate_limit_enabled=True, log_level="WARNING")


def test_rule_parsing_supports_s_m_h_d() -> None:
    assert rl.RateLimitRule.parse("10/5m") == rl.RateLimitRule(10, 300)
    assert rl.RateLimitRule.parse("5/15m") == rl.RateLimitRule(5, 900)
    assert rl.RateLimitRule.parse("100/1h") == rl.RateLimitRule(100, 3600)
    assert rl.RateLimitRule.parse("1000/1d") == rl.RateLimitRule(1000, 86400)
    assert rl.RateLimitRule.parse(" 3 / 2s ") == rl.RateLimitRule(3, 2)


@pytest.mark.parametrize("rule", ["", "10", "10/", "abc", "0/1m", "10/1x", "-5/1m"])
def test_invalid_rules_are_rejected(rule: str) -> None:
    with pytest.raises(ValueError):
        rl.RateLimitRule.parse(rule)


async def test_limiter_allows_then_blocks(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    fake = FakeRedis()
    monkeypatch.setattr(rl, "get_redis_client", lambda *_: fake)

    for _ in range(3):
        result = await rl.check_rate_limit(key="rl:test", rule="3/1m", settings=settings)
        assert result.allowed is True
        assert not result.degraded

    blocked = await rl.check_rate_limit(key="rl:test", rule="3/1m", settings=settings)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 60
    assert blocked.remaining == 0
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.headers["X-RateLimit-Remaining"] == "0"


async def test_disabled_limiter_never_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rl, "get_redis_client", lambda *_: FakeRedis())
    settings = Settings(app_env="test", rate_limit_enabled=False)
    result = await rl.check_rate_limit(key="rl:off", rule="1/1m", settings=settings)
    assert result.allowed is True


async def test_limiter_degrades_open_when_redis_is_down(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """An outage must not lock every user out; readiness reports the degradation."""
    monkeypatch.setattr(rl, "get_redis_client", lambda *_: BrokenRedis())
    result = await rl.check_rate_limit(key="rl:degraded", rule="1/1m", settings=settings)
    assert result.allowed is True
    assert result.degraded is True


def test_account_scoped_keys_hash_the_subject() -> None:
    class DummyRequest:
        headers = {"x-forwarded-for": "203.0.113.9"}
        client = None

    request = DummyRequest()  # type: ignore[assignment]
    per_ip = rl.make_rate_limit_key("auth:login", request)  # type: ignore[arg-type]
    per_account = rl.make_rate_limit_key("auth:login", request, " Holder@Example.KE ")  # type: ignore[arg-type]
    assert per_ip != per_account
    assert "holder@example.ke" not in per_account.lower()
    # Same account from a different network still shares the counter.
    again = rl.make_rate_limit_key("auth:login", request, "holder@example.ke")  # type: ignore[arg-type]
    assert again == per_account

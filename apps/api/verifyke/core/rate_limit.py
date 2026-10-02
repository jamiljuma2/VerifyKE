"""Redis-backed rate limiting.

Rules are expressed as ``"<limit>/<window>"`` (for example ``"10/5m"``). Counters
are maintained with a single Lua script so increments and expiry are atomic even
under heavy concurrency.

Failure policy: if Redis is unreachable the limiter *degrades open* (requests are
allowed) but emits a ``security.rate_limit_degraded`` warning, and the readiness
probe reports unready. This deliberately trades a small abuse window during an
outage for not locking every legitimate user out of the platform.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from redis.exceptions import RedisError

from verifyke.core.config import Settings, get_settings
from verifyke.core.errors import RateLimitError
from verifyke.core.logging import get_logger
from verifyke.core.redis_client import get_redis_client

logger = get_logger(__name__)

_WINDOW_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_RULE_RE = re.compile(r"^\s*(?P<limit>\d+)\s*/\s*(?P<amount>\d+)\s*(?P<unit>[smhd])\s*$")

# KEYS[1] = counter key, ARGV[1] = window in milliseconds
# Returns {current_count, ttl_ms}
_INCR_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('PEXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('PTTL', KEYS[1])
return {current, ttl}
"""


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    """A parsed ``limit/window`` rule."""

    limit: int
    window_seconds: int

    @classmethod
    def parse(cls, raw: str) -> RateLimitRule:
        match = _RULE_RE.match(raw)
        if not match:
            raise ValueError(f"Invalid rate limit rule: {raw!r} (expected e.g. '10/5m')")
        seconds = int(match.group("amount")) * _WINDOW_UNITS[match.group("unit")]
        if seconds <= 0 or int(match.group("limit")) <= 0:
            raise ValueError(f"Invalid rate limit rule: {raw!r}")
        return cls(limit=int(match.group("limit")), window_seconds=seconds)


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Outcome of a limiter check."""

    allowed: bool
    limit: int
    remaining: int
    retry_after_seconds: int
    degraded: bool = False

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(self.remaining, 0)),
        }
        if not self.allowed:
            headers["Retry-After"] = str(max(self.retry_after_seconds, 1))
        return headers


def client_ip(request: Request) -> str:
    """Best-effort client IP.

    Trusts ``X-Forwarded-For`` only because Nginx is the only ingress and
    overwrites the header itself; direct-to-API exposure must be prevented by
    network policy (documented in docs/security.md).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def check_rate_limit(
    *,
    key: str,
    rule: str,
    settings: Settings | None = None,
) -> RateLimitResult:
    """Consume one unit from ``key`` under ``rule``. Never raises Redis errors."""
    settings = settings or get_settings()
    parsed = RateLimitRule.parse(rule)

    if not settings.rate_limit_enabled:
        return RateLimitResult(True, parsed.limit, parsed.limit, 0)

    redis = get_redis_client(settings)
    try:
        count, ttl_ms = await redis.eval(_INCR_SCRIPT, 1, key, parsed.window_seconds * 1000)
    except (RedisError, OSError) as exc:
        logger.warning(
            "security.rate_limit_degraded",
            limiter_key=key,
            error=type(exc).__name__,
        )
        return RateLimitResult(True, parsed.limit, parsed.limit, 0, degraded=True)

    count = int(count)
    ttl_seconds = max(int(ttl_ms) // 1000, 0)
    allowed = count <= parsed.limit
    return RateLimitResult(
        allowed=allowed,
        limit=parsed.limit,
        # Never report a negative remaining budget: once the limit is exceeded the
        # useful information is Retry-After, not how far over the caller went.
        remaining=max(parsed.limit - count, 0),
        retry_after_seconds=ttl_seconds if not allowed else 0,
    )


def make_rate_limit_key(scope: str, request: Request, subject: str | None = None) -> str:
    """Build a namespaced limiter key.

    ``subject`` lets callers limit per account (for example per submitted email
    address) instead of per IP, which defends against distributed credential
    stuffing. The subject is hashed so no email address is written to Redis in
    the clear.
    """
    import hashlib

    parts = ["rl", scope, client_ip(request)]
    if subject:
        digest = hashlib.sha256(subject.strip().lower().encode("utf-8")).hexdigest()[:16]
        parts.append(digest)
    return ":".join(parts)


def rate_limit_dependency(scope: str, rule_setting: str, *, per_account: bool = False) -> Any:
    """Build a FastAPI dependency enforcing a named limit.

    ``rule_setting`` is the name of a ``Settings`` attribute (for example
    ``"rate_limit_login"``) so limits stay operator-configurable.
    """

    async def dependency(request: Request) -> Any:
        settings = get_settings()
        rule = str(getattr(settings, rule_setting))
        subject = None
        if per_account:
            subject = await _extract_subject(request)
        key = make_rate_limit_key(scope, request, subject)
        result = await check_rate_limit(key=key, rule=rule, settings=settings)
        if not result.allowed:
            logger.warning(
                "security.rate_limited",
                limiter_scope=scope,
                client_ip=client_ip(request),
                path=request.url.path,
            )
            raise RateLimitError(headers=result.headers)
        request.state.rate_limit = result
        return result

    return dependency


async def _extract_subject(request: Request) -> str | None:
    """Peek at a JSON body for an ``email``/``username`` field without consuming it."""
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return None
    try:
        body = await request.json()
    except Exception:
        return None
    if isinstance(body, dict):
        for field in ("email", "username"):
            value = body.get(field)
            if isinstance(value, str) and value:
                return value
    return None


# Dependency aliases used by feature modules (kept here so every module applies
# the same namespace and settings key).
login_rate_limit = rate_limit_dependency("auth:login", "rate_limit_login", per_account=True)
password_reset_rate_limit = rate_limit_dependency(
    "auth:password-reset", "rate_limit_password_reset", per_account=True
)
register_rate_limit = rate_limit_dependency("auth:register", "rate_limit_register")
public_verify_rate_limit = rate_limit_dependency("verify:public", "rate_limit_verify_public")
upload_verify_rate_limit = rate_limit_dependency("verify:upload", "rate_limit_verify_upload")
external_api_rate_limit = rate_limit_dependency("external:api", "rate_limit_external_api")

"""HTTP middleware: request context, access logging, security headers, limits.

Ordering matters and is asserted in ``main.py``:
    RequestContext -> SecurityHeaders -> RateLimit -> routers
so that every response (including rate-limited ones) carries a request id and
security headers.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from verifyke.core.config import get_settings
from verifyke.core.errors import RateLimitError, error_envelope
from verifyke.core.logging import (
    clear_context,
    get_logger,
    set_correlation_id,
    set_request_id,
)
from verifyke.core.rate_limit import check_rate_limit, client_ip, make_rate_limit_key

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"

# Paths excluded from the blanket rate limit (probes and docs).
_RATE_LIMIT_EXEMPT_PREFIXES = ("/health", "/ready", "/metrics", "/docs", "/redoc", "/openapi.json")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign request/correlation ids, log the completed request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming_request_id = request.headers.get(REQUEST_ID_HEADER)
        # Never trust an unbounded client-supplied id.
        if (
            incoming_request_id
            and 8 <= len(incoming_request_id) <= 64
            and incoming_request_id.isascii()
        ):
            request_id = incoming_request_id
        else:
            request_id = uuid.uuid4().hex
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or request_id

        set_request_id(request_id)
        set_correlation_id(correlation_id[:64])
        request.state.request_id = request_id

        started = time.perf_counter()
        response: Response | None = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            # The exception handlers build the error response; record the timing
            # and the 500 status here before the error propagates.
            status_code = 500
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.info(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=client_ip(request),
                user_agent=(request.headers.get("user-agent") or "")[:180],
            )
            if response is not None:
                response.headers[REQUEST_ID_HEADER] = request_id
                response.headers[CORRELATION_ID_HEADER] = correlation_id[:64]
            clear_context()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Defence-in-depth response headers.

    The API returns JSON to browser clients that also serve the web app, so the
    policy is deliberately restrictive: no framing, no sniffing, no referrer
    leakage, and a CSP that forbids everything but same-origin XHR/fetch.
    HSTS is added only in production (the web tier also sets it).
    """

    API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault(
            "Permissions-Policy", "accelerometer=(), camera=(), geolocation=(), microphone=()"
        )
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        headers.setdefault("Content-Security-Policy", self.API_CSP)
        headers.setdefault("Cache-Control", "no-store")
        if get_settings().is_production:
            headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload"
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Blanket per-IP limit. Endpoints carrying sensitive operations declare
    stricter limits through their own dependencies (see ``rate_limit.py``).
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        settings = get_settings()
        if settings.rate_limit_enabled and not path.startswith(_RATE_LIMIT_EXEMPT_PREFIXES):
            key = make_rate_limit_key("global", request)
            result = await check_rate_limit(
                key=key, rule=settings.rate_limit_default, settings=settings
            )
            if not result.allowed:
                logger.warning(
                    "security.rate_limited",
                    limiter_scope="global",
                    client_ip=client_ip(request),
                    path=path,
                )
                error = RateLimitError(headers=result.headers)
                return JSONResponse(
                    status_code=error.http_status,
                    content=error_envelope(error.code, error.message),
                    headers=result.headers,
                )
            response = await call_next(request)
            for header, value in result.headers.items():
                response.headers.setdefault(header, value)
            return response
        return await call_next(request)

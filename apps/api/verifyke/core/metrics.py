"""Prometheus metrics.

Metrics are exposed on ``/metrics`` for scraping by Prometheus (or an equivalent
collector). Only aggregate, non-identifying data is recorded - never holder
names, certificate ids or document contents. Labels are restricted to a fixed
cardinality set (method, route template, status class) to avoid label-explosion
and to keep route paths out of the metrics store.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from verifyke.core.config import get_settings

# A dedicated registry keeps the default process/platform collectors out of the
# exposition unless we choose to add them.
REGISTRY = CollectorRegistry(auto_describe=True)

HTTP_REQUESTS_TOTAL = Counter(
    "verifyke_http_requests_total",
    "Total HTTP requests processed.",
    labelnames=("method", "route", "status"),
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION = Histogram(
    "verifyke_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)

VERIFICATION_TOTAL = Counter(
    "verifyke_verification_requests_total",
    "Verification requests grouped by outcome status.",
    labelnames=("status", "channel"),
    registry=REGISTRY,
)

VERIFICATION_DURATION = Histogram(
    "verifyke_verification_duration_seconds",
    "End-to-end verification latency in seconds.",
    labelnames=("channel",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)

AUTH_EVENTS_TOTAL = Counter(
    "verifyke_auth_events_total",
    "Authentication events (login success/failure, mfa, lockout).",
    labelnames=("event", "result"),
    registry=REGISTRY,
)

SECURITY_EVENTS_TOTAL = Counter(
    "verifyke_security_events_total",
    "Security events raised by the monitoring subsystem.",
    labelnames=("event_type", "severity"),
    registry=REGISTRY,
)

RATE_LIMIT_HITS_TOTAL = Counter(
    "verifyke_rate_limit_hits_total",
    "Rate limiter rejections.",
    labelnames=("scope",),
    registry=REGISTRY,
)

DOCUMENT_PROCESSING_TOTAL = Counter(
    "verifyke_document_processing_total",
    "Document processing jobs by stage and result.",
    labelnames=("stage", "result"),
    registry=REGISTRY,
)

QUEUE_JOBS_IN_FLIGHT = Gauge(
    "verifyke_queue_jobs_in_flight",
    "Background jobs currently being processed.",
    labelnames=("queue",),
    registry=REGISTRY,
)


def render_metrics() -> tuple[bytes, str]:
    """Return the Prometheus exposition payload and its content type."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def _route_template(request: Request) -> str:
    """Route template (not the raw path) to keep label cardinality bounded."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return str(path) if path else request.url.path


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request counts and latency."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not get_settings().metrics_enabled or request.url.path == "/metrics":
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            raise
        finally:
            route = _route_template(request)
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method, route=route, status=str(status_code)
            ).inc()
            HTTP_REQUEST_DURATION.labels(method=request.method, route=route).observe(
                time.perf_counter() - started
            )

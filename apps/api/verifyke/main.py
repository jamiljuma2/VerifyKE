"""VerifyKE API application factory.

Run locally with::

    uvicorn verifyke.main:app --reload --port 8000

Design notes
------------
* Middleware is registered so the effective order (outermost first) is:
  TrustedHost -> CORS -> RequestContext -> SecurityHeaders -> RateLimit ->
  Metrics -> routes. Every response therefore carries request ids and security
  headers, including rate-limited and error responses.
* Error responses never leak internals (see ``verifyke.core.errors``).
* Startup is lazy: the database pool and Redis client connect on first use, so a
  dependency outage degrades the affected endpoints instead of preventing boot.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from verifyke import __version__
from verifyke.core.config import Settings, get_settings
from verifyke.core.db import dispose_engine
from verifyke.core.errors import register_error_handlers
from verifyke.core.logging import configure_logging, get_logger
from verifyke.core.metrics import MetricsMiddleware, render_metrics
from verifyke.core.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from verifyke.core.redis_client import close_redis, redis_available

logger = get_logger(__name__)

API_DESCRIPTION = """
VerifyKE - **Trust Every Credential. Verify Every Certificate.**

VerifyKE verifies Kenyan (and, by design, international) academic certificates
and important documents using multiple independent signals: trusted issuer
records, cryptographic signatures, content hashing, QR validation, OCR
comparison and document-structure analysis.

### Security model

* Session cookies are `HttpOnly`, `Secure` and `SameSite=Strict`; refresh tokens
  are rotated on use and stored hashed.
* Strict role-based access control with institution-level tenant isolation
  enforced in the application **and** by PostgreSQL row-level security.
* Multi-factor authentication is mandatory for administrative roles.
* Every sensitive action is written to an append-only audit log.

### Interpreting results

Verification returns a status plus the individual checks that produced it. A
`VERIFIED` result means multiple independent checks passed - it is never based on
QR code presence or OCR output alone.
"""

OPENAPI_TAGS: list[dict[str, str]] = [
    {"name": "system", "description": "Health, readiness and version probes."},
    {"name": "auth", "description": "Registration, login, MFA, sessions, password reset."},
    {"name": "institutions", "description": "Institution onboarding, approval and staff."},
    {"name": "certificates", "description": "Certificate creation, issuance and revocation."},
    {"name": "keys", "description": "Institution signing keys (rotation, versions, status)."},
    {"name": "templates", "description": "Certificate template definitions and versions."},
    {"name": "verification", "description": "Certificate and document verification."},
    {"name": "external", "description": "Machine-to-machine verification API for employers."},
    {"name": "audit", "description": "Audit log access."},
    {"name": "security", "description": "Security events and alerts."},
    {"name": "billing", "description": "Plans, subscriptions, invoices and payments."},
    {"name": "admin", "description": "Platform administration."},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown lifecycle."""
    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "service_starting",
        service="verifyke-api",
        version=__version__,
        environment=settings.app_env,
    )

    from verifyke.observability import init_error_tracking

    init_error_tracking(settings)

    if not await redis_available():
        # Not fatal: the API serves read paths and reports unready. Background
        # verification will fail until Redis returns (surfaced to the client).
        logger.warning(
            "startup_redis_unavailable", redis_url_host=settings.redis_url.split("@")[-1]
        )

    yield

    logger.info("service_stopping", service="verifyke-api")
    await close_redis()
    await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application (factory keeps tests isolated)."""
    settings = settings or get_settings()

    app = FastAPI(
        title=f"{settings.app_name} API",
        description=API_DESCRIPTION,
        version=__version__,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    register_error_handlers(app)

    # ---- middleware (last added == outermost) ----
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            settings.csrf_header_name,
            "X-Request-ID",
            "X-Correlation-ID",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-Correlation-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "Retry-After",
        ],
        max_age=600,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)

    # ---- routes ----
    from verifyke.modules.health import router as health_router

    app.include_router(health_router)
    app.include_router(health_router, prefix=settings.api_v1_prefix, include_in_schema=False)

    register_api_routers(app, settings)

    @app.get("/", include_in_schema=False)
    async def service_root() -> dict[str, Any]:
        """Minimal service banner - no configuration or topology disclosure."""
        return {
            "service": "verifyke-api",
            "version": __version__,
            "documentation": "/docs",
            "health": "/health",
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        """Prometheus exposition endpoint.

        Restricted to the internal network by Nginx (see infrastructure/nginx);
        it is never published on the public origin.
        """
        if not settings.metrics_enabled:
            return Response(status_code=404)
        payload, content_type = render_metrics()
        return Response(content=payload, media_type=content_type)

    return app


def register_api_routers(app: FastAPI, settings: Settings) -> None:
    """Attach versioned feature routers.

    Feature routers are imported lazily so that a module under construction
    cannot prevent the service (or the health endpoints) from starting.
    """
    from importlib import import_module

    module_paths = (
        # (module path, url prefix, tag)
        ("verifyke.modules.auth.router", "/auth", "auth"),
        ("verifyke.modules.institutions.router", "/institutions", "institutions"),
        ("verifyke.modules.certificates.router", "/certificates", "certificates"),
        ("verifyke.modules.verification.router", "/verify", "verification"),
        ("verifyke.modules.external.router", "/external", "external"),
        ("verifyke.modules.audit.router", "/audit-logs", "audit"),
        ("verifyke.modules.security.router", "/security", "security"),
        ("verifyke.modules.billing.router", "/billing", "billing"),
    )
    for module_path, prefix, _tag in module_paths:
        try:
            module = import_module(module_path)
        except ModuleNotFoundError as exc:
            if exc.name and exc.name.startswith("verifyke.modules"):
                logger.info("router_not_installed", module=module_path)
                continue
            raise
        router = getattr(module, "router", None)
        if router is not None:
            app.include_router(router, prefix=f"{settings.api_v1_prefix}{prefix}")


app = create_app()

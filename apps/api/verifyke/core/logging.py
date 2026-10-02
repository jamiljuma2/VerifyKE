"""Structured logging with request/correlation identifiers.

Every log line is emitted through ``structlog``. In production the renderer is
JSON (ready for CloudWatch/Loki/Datadog); in development a colourised console
renderer is used. Request-scoped context (request id, correlation id, tenant,
actor) is bound via context variables so it appears on every line without being
threaded through function signatures.

Nothing sensitive (passwords, tokens, private keys, full personal data) is ever
bound to the logging context - see ``SENSITIVE_KEYS``.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog

from verifyke.core.config import Settings, get_settings

# Keys that must never be logged, even if a caller passes them accidentally.
SENSITIVE_KEYS = frozenset(
    {
        "password",
        "new_password",
        "current_password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "secret",
        "secret_key",
        "private_key",
        "master_key",
        "mfa_secret",
        "totp_secret",
        "authorization",
        "cookie",
        "set-cookie",
    }
)

_request_id: ContextVar[str | None] = ContextVar("vk_request_id", default=None)
_correlation_id: ContextVar[str | None] = ContextVar("vk_correlation_id", default=None)
_tenant_id: ContextVar[str | None] = ContextVar("vk_tenant_id", default=None)
_actor_id: ContextVar[str | None] = ContextVar("vk_actor_id", default=None)

REDACTED = "[redacted]"


def _redact(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """structlog processor that removes sensitive values."""
    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = REDACTED
    return event_dict


def _add_context(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Attach request-scoped identifiers to every record."""
    request_id = _request_id.get()
    if request_id:
        event_dict.setdefault("request_id", request_id)
    correlation_id = _correlation_id.get()
    if correlation_id:
        event_dict.setdefault("correlation_id", correlation_id)
    tenant_id = _tenant_id.get()
    if tenant_id:
        event_dict.setdefault("institution_id", tenant_id)
    actor_id = _actor_id.get()
    if actor_id:
        event_dict.setdefault("actor_id", actor_id)
    return event_dict


def set_request_id(value: str | None) -> None:
    _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()


def set_correlation_id(value: str | None) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def bind_actor(*, actor_id: str | None, institution_id: str | None) -> None:
    """Bind the authenticated actor/tenant to the logging context."""
    _actor_id.set(actor_id)
    _tenant_id.set(institution_id)


def clear_context() -> None:
    _request_id.set(None)
    _correlation_id.set(None)
    _actor_id.set(None)
    _tenant_id.set(None)


def configure_logging(settings: Settings | None = None) -> None:
    """Configure stdlib logging and structlog. Idempotent."""
    settings = settings or get_settings()

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_context,
        _redact,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if settings.json_logs
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level,
        force=True,
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.log_level]
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route uvicorn/sqlalchemy loggers through the same renderer.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(processor=renderer, foreign_pre_chain=shared_processors)
    )
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy.engine", "alembic"):
        target = logging.getLogger(name)
        target.handlers = [handler]
        target.propagate = False
        target.setLevel(settings.log_level)

    # Access logs are emitted by our own middleware with request ids instead.
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)

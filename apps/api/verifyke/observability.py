"""Optional error-tracking integration.

Sentry is used when ``VK_SENTRY_DSN`` is set **and** the ``sentry-sdk`` package
is installed (``pip install "verifyke-api[observability]"``). When the DSN is
configured but the package is missing we log a loud warning rather than silently
pretending error tracking is active.

Personally identifiable information is never attached to events: the DSN, user
context and request bodies are explicitly disabled.
"""

from __future__ import annotations

from verifyke.core.config import Settings
from verifyke.core.logging import get_logger

logger = get_logger(__name__)


def init_error_tracking(settings: Settings) -> bool:
    """Initialise Sentry if configured and available. Returns ``True`` on success."""
    if settings.sentry_dsn is None:
        return False

    try:
        import sentry_sdk
    except ImportError:
        logger.warning(
            "error_tracking_unavailable",
            reason="VK_SENTRY_DSN is configured but sentry-sdk is not installed",
        )
        return False

    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.app_env,
        release=f"verifyke-api@{settings.app_version}",
        # Privacy: no request bodies, no cookies, no user identifiers.
        send_default_pii=False,
        traces_sample_rate=0.1 if settings.is_production else 0.0,
        attach_stacktrace=True,
        max_breadcrumbs=25,
    )
    logger.info("error_tracking_enabled", provider="sentry", environment=settings.app_env)
    return True

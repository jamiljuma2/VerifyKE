"""SQLAlchemy ORM models.

``load_all_models`` imports every model module so that ``Base.metadata`` is
complete before Alembic autogenerate runs and before SQLAlchemy resolves
relationship strings. Modules that do not exist yet are skipped, which keeps the
package importable while the platform is built up phase by phase.
"""

from __future__ import annotations

from importlib import import_module

from verifyke.core.logging import get_logger

logger = get_logger(__name__)

# Order matters only for readability; SQLAlchemy resolves relationships lazily.
MODEL_MODULES: tuple[str, ...] = (
    "verifyke.models.user",
    "verifyke.models.role",
    "verifyke.models.institution",
    "verifyke.models.key",
    "verifyke.models.template",
    "verifyke.models.certificate",
    "verifyke.models.document",
    "verifyke.models.verification",
    "verifyke.models.audit",
    "verifyke.models.security_event",
    "verifyke.models.api_client",
    "verifyke.models.billing",
    "verifyke.models.notification",
)


def load_all_models() -> list[str]:
    """Import all model modules, returning the ones that were loaded."""
    loaded: list[str] = []
    for module_path in MODEL_MODULES:
        try:
            import_module(module_path)
        except ModuleNotFoundError as exc:
            if exc.name == module_path:
                continue
            raise
        loaded.append(module_path)
    return loaded

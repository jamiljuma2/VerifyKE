"""Database engine, session management and ORM primitives.

Tenant isolation is enforced in two independent places:

1. Application level - every query goes through a repository that filters by the
   authenticated user's institution (see :mod:`verifyke.core.tenant`).
2. Database level - PostgreSQL row-level security policies key on the
   transaction-local setting ``app.current_institution`` set by
   :func:`set_tenant_context`. A developer who forgets a filter in a query still
   cannot read another institution's rows.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from uuid6 import uuid7

from verifyke.core.config import Settings, get_settings

# Deterministic constraint names keep Alembic migrations stable and readable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all VerifyKE ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def to_dict(self) -> dict[str, Any]:
        """Shallow column dictionary (never use for API responses directly)."""
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class UUIDPrimaryKeyMixin:
    """UUIDv7 primary key (time-ordered, non-sequential, non-guessable)."""

    # uuid6 provides uuid7 on Python 3.12, where the stdlib does not yet have it.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)


class TimestampMixin:
    """Created/updated timestamps maintained by the database.

    ``timestamptz`` and database defaults, per ``docs/database.md``: the value
    is UTC and cannot be shifted by the clock of whichever application server
    happened to write the row. ``updated_at`` is refreshed by a trigger rather
    than by the ORM, so a bulk SQL update cannot silently skip it.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class SoftDeleteMixin:
    """Soft deletion: records are never physically removed by application code.

    Audit and verification records have no ``deleted_at`` at all - they are
    retained, not hidden.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Return (creating on first use) the process-wide async engine."""
    global _engine
    if _engine is None:
        settings = settings or get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.db_echo,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_recycle=settings.db_pool_recycle_seconds,
            pool_pre_ping=True,
            connect_args={
                "options": f"-c statement_timeout={settings.db_statement_timeout_ms}",
                "application_name": "verifyke-api",
            },
        )
    return _engine


def get_session_factory(settings: Settings | None = None) -> async_sessionmaker[AsyncSession]:
    """Return (creating on first use) the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(settings),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session.

    The session is rolled back on error and always closed. Callers commit
    explicitly - a request that raises never leaves partial writes behind.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def set_tenant_context(session: AsyncSession, institution_id: uuid.UUID | str | None) -> None:
    """Set the transaction-local tenant for PostgreSQL row-level security.

    ``SET LOCAL`` scopes the setting to the current transaction, so a pooled
    connection can never leak one tenant's context into another request.
    Pass ``None`` for platform-level (super admin / public) operations.

    Prefer :func:`verifyke.core.tenant.apply_tenant`, which takes the request's
    :class:`~verifyke.core.tenant.TenantContext` instead of a bare id.
    """
    value = str(institution_id) if institution_id else ""
    await session.execute(
        text("SELECT set_config('app.current_institution', :value, true)"), {"value": value}
    )


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear the tenant setting for the current transaction.

    Used by platform-level operations (public verification, cross-tenant
    reporting) that must not inherit a tenant scope left on the connection.
    """
    await set_tenant_context(session, None)


async def check_database(session: AsyncSession) -> None:
    """Raise if the database is not reachable (used by the readiness probe)."""
    await session.execute(text("SELECT 1"))


async def dispose_engine() -> None:
    """Dispose the engine on shutdown (closes the connection pool)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def reset_engine_state() -> None:
    """Drop cached engine/session objects without disposing (test helper)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None

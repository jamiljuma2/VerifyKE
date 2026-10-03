"""Tenant context resolution.

The application-level half of tenant isolation: everything a request needs to
know about *which* institution it is acting for, derived from the authenticated
session rather than from client input.

PostgreSQL enforces the same boundary independently through row-level security
keyed on the ``app.current_institution`` setting that
:func:`verifyke.core.db.set_tenant_context` writes per transaction. A missed
filter in a repository is therefore a bug, not a data breach.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from verifyke.core.db import set_tenant_context
from verifyke.core.errors import PermissionDeniedError


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Who the current request is acting as.

    ``institution_id`` is ``None`` only for platform-scoped operations
    (``SUPER_ADMIN`` reporting, public verification). Those run with an empty
    RLS setting and are limited to the read-only paths that the platform-level
    policies permit.
    """

    user_id: uuid.UUID | None
    institution_id: uuid.UUID | None
    role_code: str | None

    @property
    def is_platform(self) -> bool:
        """True when no institution scope applies to this request."""
        return self.institution_id is None

    @property
    def requires_tenant(self) -> bool:
        """True when the operation must be scoped to exactly one institution."""
        return not self.is_platform

    def require_tenant(self) -> uuid.UUID:
        """Return the institution id, or refuse platform-wide access.

        Used by services that are meaningless without a tenant: signing a
        certificate, rotating a key, listing staff.
        """
        if self.institution_id is None:
            raise PermissionDeniedError(
                "This action must be performed on behalf of an institution."
            )
        return self.institution_id


async def apply_tenant(session: AsyncSession, context: TenantContext) -> None:
    """Bind the tenant context to the current transaction.

    Must be called inside the same transaction as the queries it governs:
    ``set_config(..., is_local => true)`` is transaction-scoped, which is
    exactly what stops a pooled connection from carrying one tenant's context
    into another request.
    """
    await set_tenant_context(session, context.institution_id)

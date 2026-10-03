"""Role records.

Roles are stored in a table rather than as a PostgreSQL enum on ``user`` so that
assignment history survives a role being renamed or retired, and so that an
auditor can answer "who could issue certificates on the 3rd of March?" rather
than "what does the enum say today?".

The closed set of role codes lives in :data:`ROLES` and is mirrored by the
``role_code`` PostgreSQL enum on ``user.role_code``; the table exists to give
those codes names and descriptions, not to open-endedness.
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from verifyke.core.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RoleCode(enum.StrEnum):
    """Closed set of platform roles.

    ``SUPER_ADMIN`` and ``INSTITUTION_ADMIN`` must enrol MFA before use (see
    ``VK_MFA_REQUIRED_ROLES``); ``INSTITUTION_ISSUER`` may sign certificates;
    ``VERIFIER`` and ``AUDITOR`` are read-only.
    """

    SUPER_ADMIN = "SUPER_ADMIN"
    INSTITUTION_ADMIN = "INSTITUTION_ADMIN"
    INSTITUTION_ISSUER = "INSTITUTION_ISSUER"
    VERIFIER = "VERIFIER"
    AUDITOR = "AUDITOR"


#: Roles permitted to sign a certificate for their institution.
SIGNING_ROLE_CODES = frozenset({RoleCode.INSTITUTION_ADMIN, RoleCode.INSTITUTION_ISSUER})

#: Roles that are platform-scoped rather than scoped to one institution.
PLATFORM_ROLE_CODES = frozenset({RoleCode.SUPER_ADMIN})


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named role. Seeded by migration and referenced by ``user.role_code``."""

    __tablename__ = "role"
    __table_args__ = (UniqueConstraint("code", name="uq_role_code"),)

    code: Mapped[RoleCode] = mapped_column(
        Enum(
            RoleCode,
            name="role_code",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text, default=None)

    #: Platform roles are not tied to an institution; institution roles are.
    is_platform: Mapped[bool] = mapped_column(default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Role {self.code}>"

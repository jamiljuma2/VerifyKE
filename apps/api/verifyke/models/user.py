"""User accounts.

A user is always scoped to an institution *except* for platform
``SUPER_ADMIN`` accounts, which carry a null ``institution_id`` and are covered
by the platform-level RLS policies instead (see ``docs/database.md`` section 3).

Credential material follows the rules in ``docs/security.md``:

* passwords are Argon2id hashes; the plaintext never reaches this layer;
* TOTP secrets are encrypted at rest with the master key and are stored as
  ciphertext, so a database leak does not defeat MFA;
* refresh tokens are stored as SHA-256 hashes and rotated on every use.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verifyke.core.db import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from verifyke.models.role import RoleCode


class UserStatus(enum.StrEnum):
    """Account state.

    ``LOCKED`` is set by the lockout policy after repeated failures;
    ``DISABLED`` is an administrative decision. Neither may authenticate, and
    both keep the row so the audit trail stays complete.
    """

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    LOCKED = "LOCKED"
    DISABLED = "DISABLED"


class MfaMethod(enum.StrEnum):
    """Second factors a user may enrol."""

    TOTP = "TOTP"
    RECOVERY_CODE = "RECOVERY_CODE"


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A person who can sign in: institution staff, verifiers, platform admins."""

    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("institution_id", "email", name="uq_user_institution_email"),
        # Unique on the address alone among *live* rows. The constraint above
        # cannot cover a platform SUPER_ADMIN, whose institution_id is NULL -
        # NULLs never collide in UNIQUE - and two soft-deleted users may reuse an
        # address. This partial unique index closes both gaps in the database
        # rather than trusting every caller to check first.
        Index(
            "ix_user_email_active",
            "email",
            unique=True,
            postgresql_where="deleted_at IS NULL",
        ),
        # A platform administrator has no institution; everyone else has one.
        # Enforced in both directions so a mis-provisioned row cannot grant or
        # deny platform scope by accident.
        CheckConstraint(
            "(institution_id IS NULL) = (role_code = 'SUPER_ADMIN')",
            name="ck_user_platform_requires_super_admin",
        ),
    )

    #: Null only for platform SUPER_ADMIN accounts.
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institution.id", ondelete="RESTRICT"), default=None, index=True
    )
    role_code: Mapped[RoleCode] = mapped_column(
        Enum(
            RoleCode,
            name="role_code",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_type=False,
        ),
        nullable=False,
        index=True,
    )

    #: ``citext``: sign-in must not depend on how the address was capitalised.
    email: Mapped[str] = mapped_column(CITEXT)
    full_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=UserStatus.PENDING,
        nullable=False,
        index=True,
    )

    # --- credentials (never plaintext) --------------------------------------
    password_hash: Mapped[str] = mapped_column(String(255))
    #: Argon2id parameters, so they can be upgraded without invalidating hashes.
    password_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- multi-factor -------------------------------------------------------
    mfa_method: Mapped[MfaMethod | None] = mapped_column(
        Enum(
            MfaMethod,
            name="mfa_method",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_type=False,
        ),
        default=None,
    )
    #: TOTP secret encrypted with the master key; ciphertext only.
    mfa_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    mfa_enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- lockout ------------------------------------------------------------
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- security metadata --------------------------------------------------
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[str | None] = mapped_column(String(45), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    institution: Mapped[object | None] = relationship(back_populates="users")

    @property
    def is_active(self) -> bool:
        """Whether this account may authenticate at all."""
        return self.status == UserStatus.ACTIVE and not self.is_deleted

    @property
    def is_platform(self) -> bool:
        """Whether this account is scoped to the platform rather than a tenant."""
        return self.institution_id is None

    def __repr__(self) -> str:
        return f"<User {self.email} role={self.role_code}>"

"""Institution records.

An institution is the tenant boundary: every other tenant-scoped table carries an
``institution_id`` pointing here, and PostgreSQL row-level security keys on it
(see ``docs/database.md``). Registration status is deliberately explicit - an
unapproved institution must never be able to issue certificates.
"""

from __future__ import annotations

import enum

from sqlalchemy import CheckConstraint, Enum, String, Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verifyke.core.db import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class InstitutionStatus(enum.StrEnum):
    """Lifecycle of an institution's registration.

    A ``PENDING`` institution can complete onboarding but cannot sign a
    certificate: issuance requires ``ACTIVE``. ``SUSPENDED`` keeps issued
    certificates verifiable (their holders must not lose their credentials
    because of an administrative decision) but blocks all new activity.
    """

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REJECTED = "REJECTED"


#: Institutions allowed to sign new certificates.
SIGNING_STATUSES = frozenset({InstitutionStatus.ACTIVE})


class Institution(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A registered issuing institution (university, college, examining body)."""

    __tablename__ = "institution"
    __table_args__ = (
        # The issuing country drives the certificate-number segment and the
        # regulator lookup, so a two-letter code is enforced rather than assumed.
        CheckConstraint(
            "char_length(country_code) = 2",
            name="ck_institution_country_code_length",
        ),
    )

    #: Case-insensitive short identifier used in URLs and API paths.
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[InstitutionStatus] = mapped_column(
        Enum(
            InstitutionStatus,
            name="institution_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=InstitutionStatus.PENDING,
        nullable=False,
        index=True,
    )

    # --- regulatory identity -------------------------------------------------
    country_code: Mapped[str] = mapped_column(String(2))
    regulator_name: Mapped[str | None] = mapped_column(String(255), default=None)
    #: ISO 4217 code of the jurisdiction's regulator, where it differs from country.
    regulator_code: Mapped[str | None] = mapped_column(String(16), default=None)

    # --- contact -------------------------------------------------------------
    #: ``citext``: an institution is identified by email case-insensitively.
    contact_email: Mapped[str] = mapped_column(CITEXT)
    contact_phone: Mapped[str | None] = mapped_column(String(32), default=None)
    website: Mapped[str | None] = mapped_column(String(255), default=None)

    # --- address -------------------------------------------------------------
    address_line: Mapped[str | None] = mapped_column(String(255), default=None)
    city: Mapped[str | None] = mapped_column(String(120), default=None)
    postal_code: Mapped[str | None] = mapped_column(String(32), default=None)

    #: Earliest certificate number issued, for display only - not an identifier.
    certificate_prefix: Mapped[str | None] = mapped_column(String(16), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    users: Mapped[list[object]] = relationship(back_populates="institution")
    keys: Mapped[list[object]] = relationship(back_populates="institution")

    @property
    def can_sign(self) -> bool:
        """Whether this institution may sign new certificates right now."""
        return self.status in SIGNING_STATUSES and not self.is_deleted

    def __repr__(self) -> str:
        return f"<Institution {self.slug} status={self.status}>"

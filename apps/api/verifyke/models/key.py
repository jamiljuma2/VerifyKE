"""Institution signing keys (one row per version).

This is the persisted form of :class:`verifyke_security.keys.KeyVersion`. The
private half is stored only as AES-256-GCM ciphertext wrapped under the master
key; the AAD binds the ciphertext to this row's institution and version, so a
wrapped key copied into another row fails to unwrap.

Versioning is what makes rotation safe: a certificate records the key version
it was signed with, so retiring a key never invalidates what was already
issued (see ``docs/security.md`` section 5).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from verifyke.core.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KeyStatus(enum.StrEnum):
    """Lifecycle of one key version.

    ``ACTIVE``      - current key; may sign.
    ``RETIRED``     - no longer signs, but still verifies certificates issued with it.
    ``COMPROMISED`` - must never be trusted; affected certificates are re-issued.
    """

    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    COMPROMISED = "COMPROMISED"


class InstitutionKey(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A versioned Ed25519 signing key belonging to one institution."""

    __tablename__ = "institution_key"
    __table_args__ = (
        UniqueConstraint("institution_id", "version", name="uq_institution_key_version"),
        CheckConstraint("version >= 1", name="ck_institution_key_version_positive"),
    )

    institution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("institution.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[KeyStatus] = mapped_column(
        Enum(
            KeyStatus,
            name="institution_key_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=KeyStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    #: Raw 32-byte Ed25519 public key - safe to store and to publish.
    public_key: Mapped[bytes] = mapped_column(LargeBinary)
    #: nonce || ciphertext || tag (60 bytes), as produced by verifyke_security.
    wrapped_private_key: Mapped[bytes] = mapped_column(LargeBinary)
    #: How the private key is protected (currently only the local master key).
    key_provider: Mapped[str] = mapped_column(String(32), default="local", nullable=False)
    #: Provider-side key reference when the provider is not local (e.g. a KMS id).
    provider_key_ref: Mapped[str | None] = mapped_column(String(255), default=None)

    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Recorded when a key is marked compromised, for the incident procedure.
    compromised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    institution: Mapped[object] = relationship(back_populates="keys")

    @property
    def allows_signing(self) -> bool:
        """Only an ``ACTIVE`` key may produce new signatures."""
        return self.status == KeyStatus.ACTIVE

    def __repr__(self) -> str:
        return f"<InstitutionKey institution={self.institution_id} v{self.version} {self.status}>"

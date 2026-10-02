"""The VerifyKE key hierarchy: master key -> institution keys -> signatures.

Threat this answers: *whoever holds an institution's signing key can forge
certificates for that institution.* The design (see ``docs/security.md``):

* Each institution owns versioned Ed25519 key pairs. Only the **public** half
  and the **wrapped** private half are ever stored.
* Private keys are wrapped with AES-256-GCM under a single 32-byte **master
  key** (``VK_MASTER_KEY``) held in secret storage, never in the database.
  The GCM associated data (AAD) binds a wrapped key to its institution and
  version, so a wrapped blob copied to another row fails to unwrap.
* A key version has a status: ``active`` (may sign), ``retired`` (kept only to
  verify certificates already issued with it) or ``compromised`` (must be
  excluded from trust decisions; see ``docs/security.md`` for the procedure).

This module is deliberately independent of the API's configuration and
database: callers pass key material explicitly, which keeps the crypto
testable in isolation and free of import-time settings.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .errors import InvalidKeyStatusError, KeyMaterialError, KeyWrapError

ED25519_KEY_SIZE: Final = 32
MASTER_KEY_SIZE: Final = 32
NONCE_SIZE: Final = 12
GCM_TAG_SIZE: Final = 16

# nonce || (ciphertext || tag) for a 32-byte private key seed.
WRAPPED_KEY_SIZE: Final = NONCE_SIZE + GCM_TAG_SIZE + ED25519_KEY_SIZE


class KeyStatus(StrEnum):
    """Lifecycle of an institution key version."""

    ACTIVE = "active"
    RETIRED = "retired"
    COMPROMISED = "compromised"

    @classmethod
    def parse(cls, value: str | KeyStatus) -> KeyStatus:
        """Coerce a stored string (or member) to a :class:`KeyStatus`."""
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise InvalidKeyStatusError(f"unknown key status: {value!r}") from exc


def generate_private_key() -> bytes:
    """Generate a fresh Ed25519 private key (32-byte seed)."""
    return Ed25519PrivateKey.generate().private_bytes_raw()


def public_key_from_private(private_key: bytes) -> bytes:
    """Derive the 32-byte public key for ``private_key``."""
    return _coerce_private(private_key).public_key().public_bytes_raw()


def _coerce_private(private_key: bytes) -> Ed25519PrivateKey:
    if not isinstance(private_key, bytes) or len(private_key) != ED25519_KEY_SIZE:
        raise KeyMaterialError(f"Ed25519 private key must be exactly {ED25519_KEY_SIZE} bytes")
    try:
        return Ed25519PrivateKey.from_private_bytes(private_key)
    except ValueError as exc:
        raise KeyMaterialError("bytes are not a valid Ed25519 private key") from exc


def require_master_key(master_key: bytes) -> bytes:
    """Validate and return the 32-byte master key material."""
    if not isinstance(master_key, bytes) or len(master_key) != MASTER_KEY_SIZE:
        raise KeyMaterialError(f"master key must be exactly {MASTER_KEY_SIZE} bytes (AES-256)")
    return master_key


def key_aad(institution_id: str, version: int) -> bytes:
    """Canonical AAD binding a wrapped key to its institution and version.

    The same derivation must be used at wrap time and unwrap time; storing the
    institution id and version alongside the wrapped blob makes that automatic.
    """
    if not institution_id.strip():
        raise KeyMaterialError("institution_id must not be empty")
    if version < 1:
        raise KeyMaterialError("key version must be >= 1")
    return f"verifyke:institution-key:{institution_id}:v{version}".encode()


def wrap_private_key(private_key: bytes, master_key: bytes, *, aad: bytes = b"") -> bytes:
    """Wrap a private key with AES-256-GCM under the master key.

    Returns ``nonce || ciphertext || tag``. A fresh random nonce is used for
    every wrap, so wrapping the same key twice yields different bytes.
    """
    _coerce_private(private_key)
    require_master_key(master_key)
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = AESGCM(master_key).encrypt(nonce, private_key, aad)
    return nonce + ciphertext


@dataclass(frozen=True, slots=True)
class KeyVersion:
    """An institution key version as stored: public, wrapped, and statused."""

    version: int
    public_key: bytes
    wrapped_private_key: bytes
    status: KeyStatus = KeyStatus.ACTIVE

    def __post_init__(self) -> None:
        if not isinstance(self.version, int) or self.version < 1:
            raise KeyMaterialError("key version must be an integer >= 1")
        if len(self.public_key) != ED25519_KEY_SIZE:
            raise KeyMaterialError(f"public key must be exactly {ED25519_KEY_SIZE} bytes")
        if len(self.wrapped_private_key) != WRAPPED_KEY_SIZE:
            raise KeyMaterialError(f"wrapped private key must be exactly {WRAPPED_KEY_SIZE} bytes")
        object.__setattr__(self, "status", KeyStatus.parse(self.status))

    @property
    def allows_signing(self) -> bool:
        """Only ``active`` keys may produce new signatures."""
        return self.status == KeyStatus.ACTIVE

    def ensure_signable(self) -> None:
        """Raise :class:`InvalidKeyStatusError` unless this key may sign."""
        if not self.allows_signing:
            raise InvalidKeyStatusError(
                f"key version {self.version} is {self.status.value} and cannot sign"
            )


def create_key_version(
    version: int,
    master_key: bytes,
    *,
    aad: bytes = b"",
) -> tuple[KeyVersion, bytes]:
    """Generate, wrap and describe a new key version.

    Returns the stored :class:`KeyVersion` plus the plaintext private key for
    the caller that will sign immediately; the plaintext never leaves the
    process and must not be persisted.
    """
    private_key = generate_private_key()
    record = KeyVersion(
        version=version,
        public_key=public_key_from_private(private_key),
        wrapped_private_key=wrap_private_key(private_key, master_key, aad=aad),
    )
    return record, private_key


def signing_private_key(
    key: KeyVersion,
    master_key: bytes,
    *,
    aad: bytes = b"",
) -> bytes:
    """Unwrap a key version for signing, enforcing status and consistency.

    Raises :class:`InvalidKeyStatusError` for retired/compromised keys and
    :class:`KeyWrapError` if the unwrapped key does not match the recorded
    public key (defence against a swapped ciphertext).
    """
    key.ensure_signable()
    private_key = unwrap_private_key(key.wrapped_private_key, master_key, aad=aad)
    if public_key_from_private(private_key) != key.public_key:
        raise KeyWrapError("unwrapped private key does not match the recorded public key")
    return private_key


def unwrap_private_key(wrapped: bytes, master_key: bytes, *, aad: bytes = b"") -> bytes:
    """Authenticate and unwrap a private key.

    Raises :class:`~verifyke_security.errors.KeyWrapError` when the master key
    is wrong, the AAD does not match, or the ciphertext was tampered with -
    the three cases GCM cannot tell apart, reported as one honest message.
    """
    require_master_key(master_key)
    if not isinstance(wrapped, bytes) or len(wrapped) != WRAPPED_KEY_SIZE:
        raise KeyWrapError(
            f"wrapped key must be exactly {WRAPPED_KEY_SIZE} bytes, "
            f"got {len(wrapped) if isinstance(wrapped, bytes) else type(wrapped).__name__}"
        )
    nonce, ciphertext = wrapped[:NONCE_SIZE], wrapped[NONCE_SIZE:]
    try:
        private_key = AESGCM(master_key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise KeyWrapError(
            "wrapped key failed authentication (wrong master key, AAD, or tampered data)"
        ) from exc
    # Any 32-byte value is a valid Ed25519 seed; length was fixed by the wrap.
    return private_key

"""Ed25519 signing and verification of canonical payloads.

A signature always covers the RFC 8785 canonical bytes of the payload (see
:mod:`verifyke_security.canonicalisation`), never a caller-chosen serialisation,
so verification is byte-exact on every platform.

The envelope produced by :func:`sign` is JSON-ready for storage next to the
certificate row::

    {"alg": "Ed25519", "payload_hash": "<sha256 hex>", "signature": "<b64url>",
     "key_id": "<optional caller-supplied hint>"}

Only ``alg`` and ``signature`` are verified structurally; ``payload_hash`` is
consistency metadata checked after the signature, and ``key_id`` is a hint the
caller resolves (verification always receives the right public key from the
certificate's recorded key version).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .canonicalisation import JsonValue, canonical_json
from .encoding import b64u_decode, b64u_encode
from .errors import EncodingError, KeyMaterialError, SecurityError, SignatureError
from .hashing import constant_time_equals, sha256_hex
from .keys import ED25519_KEY_SIZE, public_key_from_private

ALGORITHM: Final = "Ed25519"
SIGNATURE_SIZE: Final = 64


def sign_bytes(message: bytes, private_key: bytes) -> bytes:
    """Sign raw ``message`` bytes with an Ed25519 private key."""
    key = _coerce_private(private_key)
    if not isinstance(message, bytes):
        raise SignatureError("message must be bytes")
    return key.sign(message)


def verify_bytes(message: bytes, signature: bytes, public_key: bytes) -> None:
    """Verify a raw signature over ``message``; raise ``SignatureError`` if invalid."""
    key = _coerce_public(public_key)
    if not isinstance(message, bytes):
        raise SignatureError("message must be bytes")
    if not isinstance(signature, bytes) or len(signature) != SIGNATURE_SIZE:
        raise SignatureError(
            f"signature must be exactly {SIGNATURE_SIZE} bytes, "
            f"got {len(signature) if isinstance(signature, bytes) else type(signature).__name__}"
        )
    try:
        key.verify(signature, message)
    except InvalidSignature as exc:
        raise SignatureError(
            "signature does not verify against the payload and public key"
        ) from exc


def sign(payload: JsonValue, private_key: bytes, *, key_id: str | None = None) -> dict[str, str]:
    """Canonicalise ``payload`` and sign it, returning a JSON-ready envelope.

    Ed25519 is deterministic, so the same payload and key always produce the
    same envelope (which makes issuance idempotent for a given key version).
    """
    message = canonical_json(payload)
    signature = sign_bytes(message, private_key)
    envelope: dict[str, str] = {
        "alg": ALGORITHM,
        "payload_hash": sha256_hex(message),
        "signature": b64u_encode(signature),
    }
    if key_id is not None:
        if not key_id.strip():
            raise SignatureError("key_id must be a non-empty string when provided")
        envelope["key_id"] = key_id
    return envelope


def verify(payload: JsonValue, envelope: Mapping[str, Any], public_key: bytes) -> None:
    """Verify ``envelope`` against ``payload`` and the given public key.

    Raises :class:`~verifyke_security.errors.SignatureError` for a missing or
    malformed envelope, an unsupported algorithm, a mismatched signature or an
    inconsistent ``payload_hash``; ``CanonicalisationError`` propagates if the
    payload is not valid JSON data.
    """
    if not isinstance(envelope, Mapping):
        raise SignatureError("envelope must be a mapping")

    algorithm = envelope.get("alg")
    if algorithm != ALGORITHM:
        raise SignatureError(f"unsupported signature algorithm: {algorithm!r}")

    raw_signature = envelope.get("signature")
    if not isinstance(raw_signature, str):
        raise SignatureError("envelope is missing the signature")
    try:
        signature = b64u_decode(raw_signature)
    except EncodingError as exc:
        raise SignatureError("signature is not valid base64url") from exc

    message = canonical_json(payload)
    verify_bytes(message, signature, public_key)

    expected_hash = envelope.get("payload_hash")
    if expected_hash is not None and expected_hash != sha256_hex(message):
        raise SignatureError("envelope payload hash does not match the payload")


def is_valid(payload: JsonValue, envelope: Mapping[str, Any], public_key: bytes) -> bool:
    """Boolean convenience wrapper around :func:`verify`."""
    try:
        verify(payload, envelope, public_key)
    except SecurityError:
        return False
    return True


def signature_for(payload: JsonValue, private_key: bytes) -> bytes:
    """Raw signature bytes over the canonical payload (no envelope)."""
    return sign_bytes(canonical_json(payload), private_key)


def public_key_matches(private_key: bytes, public_key: bytes) -> bool:
    """Whether a private key derives the given public key (constant-time)."""
    return constant_time_equals(public_key_from_private(private_key), public_key)


def _coerce_private(private_key: bytes) -> Ed25519PrivateKey:
    if not isinstance(private_key, bytes) or len(private_key) != ED25519_KEY_SIZE:
        raise KeyMaterialError(f"Ed25519 private key must be exactly {ED25519_KEY_SIZE} bytes")
    try:
        return Ed25519PrivateKey.from_private_bytes(private_key)
    except ValueError as exc:
        raise KeyMaterialError("bytes are not a valid Ed25519 private key") from exc


def _coerce_public(public_key: bytes) -> Ed25519PublicKey:
    if not isinstance(public_key, bytes) or len(public_key) != ED25519_KEY_SIZE:
        raise KeyMaterialError(f"Ed25519 public key must be exactly {ED25519_KEY_SIZE} bytes")
    try:
        return Ed25519PublicKey.from_public_bytes(public_key)
    except ValueError as exc:
        raise KeyMaterialError("bytes are not a valid Ed25519 public key") from exc

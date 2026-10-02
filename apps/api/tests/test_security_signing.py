"""Ed25519 signing and verification of canonical payloads."""

from __future__ import annotations

import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from verifyke_security import (
    ALGORITHM,
    KeyMaterialError,
    SignatureError,
    canonical_json,
    generate_private_key,
    is_sha256_hex,
    is_valid,
    public_key_from_private,
    public_key_matches,
    sign,
    sign_bytes,
    signature_for,
    verify,
    verify_bytes,
)

PAYLOAD = {
    "certificate_number": "VK-KE-2026-7FQ2M9XB4KD1-Q",
    "holder": "Wanjiku Kamau",
    "award": "BSc Computer Science",
    "year": 2026,
    "graduated": True,
    "grades": [{"unit": "Algorithms", "mark": 78}],
}


def _keypair() -> tuple[bytes, bytes]:
    private = generate_private_key()
    return private, public_key_from_private(private)


def test_sign_then_verify_round_trip() -> None:
    private, public = _keypair()
    envelope = sign(PAYLOAD, private, key_id="v1")
    assert envelope["alg"] == ALGORITHM
    assert envelope["key_id"] == "v1"
    assert is_sha256_hex(envelope["payload_hash"])
    verify(PAYLOAD, envelope, public)  # must not raise


def test_envelope_is_json_serialisable() -> None:
    private, _public = _keypair()
    envelope = sign(PAYLOAD, private)
    assert json.loads(json.dumps(envelope)) == envelope


def test_verification_tolerates_key_order_differences() -> None:
    private, public = _keypair()
    envelope = sign(PAYLOAD, private)
    reordered = dict(reversed(list(PAYLOAD.items())))
    verify(reordered, envelope, public)


def test_modified_payload_fails_verification() -> None:
    private, public = _keypair()
    envelope = sign(PAYLOAD, private)
    tampered = {**PAYLOAD, "holder": "Someone Else"}
    with pytest.raises(SignatureError, match="does not verify"):
        verify(tampered, envelope, public)
    assert not is_valid(tampered, envelope, public)


def test_wrong_public_key_fails() -> None:
    private, _public = _keypair()
    envelope = sign(PAYLOAD, private)
    other_public = public_key_from_private(generate_private_key())
    with pytest.raises(SignatureError, match="does not verify"):
        verify(PAYLOAD, envelope, other_public)


def test_signing_is_deterministic() -> None:
    """Ed25519 is deterministic: re-issuing the same payload gives the bytes."""
    private, _public = _keypair()
    assert sign(PAYLOAD, private) == sign(PAYLOAD, private)


def test_empty_key_id_is_rejected() -> None:
    private, _public = _keypair()
    with pytest.raises(SignatureError, match="key_id"):
        sign(PAYLOAD, private, key_id="   ")


def test_missing_or_malformed_envelopes_are_rejected() -> None:
    private, public = _keypair()
    envelope = sign(PAYLOAD, private)
    with pytest.raises(SignatureError, match="mapping"):
        verify(PAYLOAD, "not-a-mapping", public)  # type: ignore[arg-type]
    with pytest.raises(SignatureError, match="unsupported signature algorithm"):
        verify(PAYLOAD, {}, public)
    with pytest.raises(SignatureError, match="unsupported signature algorithm"):
        verify(PAYLOAD, {"alg": "HS256", "signature": envelope["signature"]}, public)
    with pytest.raises(SignatureError, match="missing the signature"):
        verify(PAYLOAD, {"alg": ALGORITHM}, public)


def test_non_base64url_signature_is_rejected() -> None:
    _private, public = _keypair()
    broken = {"alg": ALGORITHM, "signature": "not base64!"}
    with pytest.raises(SignatureError, match="base64url"):
        verify(PAYLOAD, broken, public)


def test_payload_hash_inconsistency_is_rejected() -> None:
    private, public = _keypair()
    envelope = sign(PAYLOAD, private)
    drifted = {**envelope, "payload_hash": "0" * 64}
    with pytest.raises(SignatureError, match="payload hash"):
        verify(PAYLOAD, drifted, public)


def test_raw_byte_signing_helpers() -> None:
    private, public = _keypair()
    message = b"raw message"
    signature = sign_bytes(message, private)
    verify_bytes(message, signature, public)
    with pytest.raises(SignatureError, match="does not verify"):
        verify_bytes(b"another message", signature, public)
    with pytest.raises(SignatureError, match="64 bytes"):
        verify_bytes(message, signature[:10], public)
    with pytest.raises(KeyMaterialError, match="32 bytes"):
        sign_bytes(message, b"short")


def test_signature_agrees_with_the_cryptography_library() -> None:
    """Our envelopes carry exactly what cryptography computes directly."""
    private, _public = _keypair()
    key = Ed25519PrivateKey.from_private_bytes(private)
    raw = canonical_json(PAYLOAD)
    assert key.sign(raw) == signature_for(PAYLOAD, private)


def test_public_key_matches() -> None:
    private, public = _keypair()
    assert public_key_matches(private, public)
    assert not public_key_matches(private, public_key_from_private(generate_private_key()))


def test_is_valid_returns_false_for_any_security_error() -> None:
    private, public = _keypair()
    envelope = sign(PAYLOAD, private)
    assert is_valid(PAYLOAD, envelope, public)
    assert not is_valid(PAYLOAD, envelope, b"bad-key")
    assert not is_valid(PAYLOAD, {}, public)

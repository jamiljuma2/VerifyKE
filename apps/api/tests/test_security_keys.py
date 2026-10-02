"""Key hierarchy: generation, wrapping, status enforcement."""

from __future__ import annotations

import pytest

from verifyke_security import (
    ED25519_KEY_SIZE,
    WRAPPED_KEY_SIZE,
    InvalidKeyStatusError,
    KeyMaterialError,
    KeyStatus,
    KeyVersion,
    KeyWrapError,
    create_key_version,
    generate_private_key,
    key_aad,
    public_key_from_private,
    require_master_key,
    sign_bytes,
    signing_private_key,
    unwrap_private_key,
    verify_bytes,
    wrap_private_key,
)

MASTER_KEY = bytes(range(32))
OTHER_MASTER_KEY = bytes(range(1, 33))


def _record(version: int = 1, status: KeyStatus = KeyStatus.ACTIVE) -> tuple[KeyVersion, bytes]:
    private = generate_private_key()
    record = KeyVersion(
        version=version,
        public_key=public_key_from_private(private),
        wrapped_private_key=wrap_private_key(private, MASTER_KEY),
        status=status,
    )
    return record, private


def test_master_key_must_be_32_bytes() -> None:
    assert require_master_key(MASTER_KEY) == MASTER_KEY
    with pytest.raises(KeyMaterialError, match="32 bytes"):
        require_master_key(b"short")
    with pytest.raises(KeyMaterialError, match="32 bytes"):
        require_master_key("x" * 32)  # type: ignore[arg-type]


def test_generated_key_is_32_bytes_and_derives_a_public_key() -> None:
    private = generate_private_key()
    assert len(private) == ED25519_KEY_SIZE
    public = public_key_from_private(private)
    assert len(public) == ED25519_KEY_SIZE
    assert public != private
    # Two generations never collide in practice.
    assert public_key_from_private(generate_private_key()) != public


def test_private_key_length_is_validated() -> None:
    with pytest.raises(KeyMaterialError, match="32 bytes"):
        public_key_from_private(b"nope")


def test_wrap_unwrap_round_trip() -> None:
    private = generate_private_key()
    wrapped = wrap_private_key(private, MASTER_KEY)
    assert len(wrapped) == WRAPPED_KEY_SIZE
    assert unwrap_private_key(wrapped, MASTER_KEY) == private


def test_wrapping_is_randomised() -> None:
    """A fresh nonce per wrap means identical keys never share ciphertext."""
    private = generate_private_key()
    assert wrap_private_key(private, MASTER_KEY) != wrap_private_key(private, MASTER_KEY)


def test_wrong_master_key_fails_authentication() -> None:
    wrapped = wrap_private_key(generate_private_key(), MASTER_KEY)
    with pytest.raises(KeyWrapError, match="failed authentication"):
        unwrap_private_key(wrapped, OTHER_MASTER_KEY)


def test_wrong_aad_fails_authentication() -> None:
    """A wrapped key cannot be moved to another institution's row."""
    private = generate_private_key()
    wrapped = wrap_private_key(private, MASTER_KEY, aad=key_aad("inst_a", 1))
    with pytest.raises(KeyWrapError, match="failed authentication"):
        unwrap_private_key(wrapped, MASTER_KEY, aad=key_aad("inst_b", 1))
    with pytest.raises(KeyWrapError, match="failed authentication"):
        unwrap_private_key(wrapped, MASTER_KEY, aad=key_aad("inst_a", 2))
    assert unwrap_private_key(wrapped, MASTER_KEY, aad=key_aad("inst_a", 1)) == private


def test_tampered_wrapped_key_fails_authentication() -> None:
    wrapped = bytearray(wrap_private_key(generate_private_key(), MASTER_KEY))
    wrapped[-1] ^= 0x01
    with pytest.raises(KeyWrapError, match="failed authentication"):
        unwrap_private_key(bytes(wrapped), MASTER_KEY)


def test_wrapped_key_length_is_validated() -> None:
    with pytest.raises(KeyWrapError, match="exactly"):
        unwrap_private_key(b"short", MASTER_KEY)
    with pytest.raises(KeyWrapError, match="exactly"):
        unwrap_private_key(MASTER_KEY, MASTER_KEY)


def test_key_aad_derivation() -> None:
    assert key_aad("inst_123", 2) == b"verifyke:institution-key:inst_123:v2"
    assert key_aad("inst_123", 2) == key_aad("inst_123", 2)
    with pytest.raises(KeyMaterialError, match="institution_id"):
        key_aad("   ", 1)
    with pytest.raises(KeyMaterialError, match="version"):
        key_aad("inst", 0)


def test_key_version_validates_its_fields() -> None:
    record, _private = _record()
    assert record.version == 1
    assert record.status == KeyStatus.ACTIVE
    assert record.allows_signing
    with pytest.raises(KeyMaterialError, match="version"):
        KeyVersion(
            version=0,
            public_key=record.public_key,
            wrapped_private_key=record.wrapped_private_key,
        )
    with pytest.raises(KeyMaterialError, match="public key"):
        KeyVersion(
            version=1,
            public_key=b"x" * 31,
            wrapped_private_key=record.wrapped_private_key,
        )
    with pytest.raises(KeyMaterialError, match="wrapped private key"):
        KeyVersion(version=1, public_key=record.public_key, wrapped_private_key=b"y" * 10)


def test_status_parsing_and_coercion() -> None:
    assert KeyStatus.parse("retired") == KeyStatus.RETIRED
    assert KeyStatus.parse(KeyStatus.COMPROMISED) == KeyStatus.COMPROMISED
    with pytest.raises(InvalidKeyStatusError, match="unknown key status"):
        KeyStatus.parse("pending")


def test_stored_string_status_is_coerced_on_the_record() -> None:
    record, _private = _record()
    coerced = KeyVersion(
        version=record.version,
        public_key=record.public_key,
        wrapped_private_key=record.wrapped_private_key,
        status="retired",  # type: ignore[arg-type]
    )
    assert coerced.status == KeyStatus.RETIRED


def test_retired_and_compromised_keys_cannot_sign() -> None:
    for status in (KeyStatus.RETIRED, KeyStatus.COMPROMISED):
        record, _private = _record(status=status)
        assert not record.allows_signing
        with pytest.raises(InvalidKeyStatusError, match="cannot sign"):
            record.ensure_signable()
        with pytest.raises(InvalidKeyStatusError, match="cannot sign"):
            signing_private_key(record, MASTER_KEY)


def test_create_key_version_wraps_and_returns_the_private_key() -> None:
    aad = key_aad("inst_1", 1)
    record, private = create_key_version(1, MASTER_KEY, aad=aad)
    assert record.version == 1
    assert record.status == KeyStatus.ACTIVE
    assert record.public_key == public_key_from_private(private)
    assert signing_private_key(record, MASTER_KEY, aad=aad) == private
    # The record on its own is useless without the master key.
    with pytest.raises(KeyWrapError):
        signing_private_key(record, OTHER_MASTER_KEY, aad=aad)


def test_signing_key_detects_swapped_ciphertext() -> None:
    a_record, _a_private = create_key_version(1, MASTER_KEY)
    b_record, _b_private = create_key_version(2, MASTER_KEY)
    forged = KeyVersion(
        version=a_record.version,
        public_key=a_record.public_key,
        wrapped_private_key=b_record.wrapped_private_key,
    )
    with pytest.raises(KeyWrapError, match="does not match"):
        signing_private_key(forged, MASTER_KEY)


def test_public_key_is_usable_without_unwrapping() -> None:
    """Verification never needs the private key (or the master key)."""
    record, private = _record()
    signature = sign_bytes(b"payload", private)
    verify_bytes(b"payload", signature, record.public_key)

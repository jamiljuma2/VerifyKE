"""SHA-256 hashing helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from verifyke_security import (
    constant_time_equals,
    is_sha256_hex,
    sha256_digest,
    sha256_file,
    sha256_hex,
    sha256_stream,
)

ABC_HEX = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_known_sha256_vector() -> None:
    """The published SHA-256 digest of ``abc`` must match exactly."""
    assert sha256_hex(b"abc") == ABC_HEX
    assert sha256_digest(b"abc").hex() == ABC_HEX


def test_stream_hashing_equals_single_shot() -> None:
    data = b"x" * 10_000
    assert sha256_stream([data[:1000], data[1000:]]) == sha256_hex(data)
    assert sha256_stream(chunk for chunk in (b"a", b"b", b"c")) == sha256_hex(b"abc")
    assert sha256_stream([]) == sha256_hex(b"")


def test_file_hashing_matches_bytes(tmp_path: Path) -> None:
    payload = b"certificate-bytes" * 1000
    target = tmp_path / "document.bin"
    target.write_bytes(payload)
    assert sha256_file(target) == sha256_hex(payload)
    # A chunk size that does not divide the file must not change the digest.
    assert sha256_file(target, chunk_size=7) == sha256_hex(payload)


def test_invalid_chunk_size_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "document.bin"
    target.write_bytes(b"x")
    with pytest.raises(ValueError, match="chunk_size"):
        sha256_file(target, chunk_size=0)


def test_constant_time_equals() -> None:
    assert constant_time_equals(b"digest", b"digest")
    assert not constant_time_equals(b"digest", b"digesT")
    assert not constant_time_equals(b"digest", b"shorter")
    assert constant_time_equals(b"", b"")


def test_is_sha256_hex_predicate() -> None:
    assert is_sha256_hex(ABC_HEX)
    assert is_sha256_hex(ABC_HEX.upper())
    assert not is_sha256_hex("deadbeef")
    assert not is_sha256_hex("g" * 64)
    assert not is_sha256_hex(ABC_HEX[:-1])
    assert not is_sha256_hex(None)
    assert not is_sha256_hex(12345)

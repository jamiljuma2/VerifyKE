"""SHA-256 content hashing.

Issued certificates and uploaded documents are identified by the SHA-256 of
their *exact bytes*: the hash is what the verification engine compares against
the issuer's stored digest, so hashing is streaming (files can be gigabytes)
and comparison is constant-time (no timing side channel on digests).
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable
from pathlib import Path
from typing import Final

CHUNK_SIZE: Final = 1024 * 1024
SHA256_HEX_LENGTH: Final = 64
SHA256_DIGEST_LENGTH: Final = 32

_HEX_DIGITS: Final = frozenset("0123456789abcdefABCDEF")


def sha256_digest(data: bytes | bytearray | memoryview) -> bytes:
    """Raw SHA-256 digest of ``data``."""
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes | bytearray | memoryview) -> str:
    """Lowercase hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def sha256_stream(chunks: Iterable[bytes]) -> str:
    """Lowercase hex SHA-256 over an iterable of chunks (generator friendly)."""
    digest = hashlib.sha256()
    for chunk in chunks:
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: str | Path, *, chunk_size: int = CHUNK_SIZE) -> str:
    """Lowercase hex SHA-256 of a file, read in bounded chunks.

    Raises ``ValueError`` for a non-positive ``chunk_size`` and lets OS errors
    (``FileNotFoundError`` etc.) propagate - those are caller bugs, not
    security failures.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def constant_time_equals(left: bytes, right: bytes) -> bool:
    """Compare two byte strings without leaking their difference via timing."""
    return hmac.compare_digest(left, right)


def is_sha256_hex(value: object) -> bool:
    """Whether ``value`` looks like a SHA-256 digest in hex (case-insensitive)."""
    if not isinstance(value, str) or len(value) != SHA256_HEX_LENGTH:
        return False
    return all(char in _HEX_DIGITS for char in value)

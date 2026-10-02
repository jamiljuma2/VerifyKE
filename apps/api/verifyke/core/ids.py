"""Identifier primitives.

VerifyKE never exposes sequential database identifiers to clients. Primary keys
are UUIDv7 (time-ordered, non-guessable), and public certificate identifiers are
random, checksum-protected Crockford base32 strings of the documented form
``VK-KE-2026-XXXXXXXXXXXX-C``.

The country segment is a configuration-free constant for now (``KE``); the
issuer country is recorded on the institution record for multi-country rollout.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime

from uuid6 import uuid7

# Crockford base32: no I, L, O or U, so digits cannot be confused when a
# certificate id is read aloud, printed or typed by a human.
CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

CERTIFICATE_ID_PREFIX = "VK"
DEFAULT_COUNTRY_CODE = "KE"
CERTIFICATE_ID_RANDOM_LENGTH = 12


def utcnow() -> datetime:
    """Timezone-aware current UTC time (never use naive datetimes in VerifyKE)."""
    return datetime.now(UTC)


def new_uuid() -> uuid.UUID:
    """New UUIDv7 primary key."""
    return uuid7()


def new_uuid_str() -> str:
    """New UUIDv7 primary key as a string."""
    return str(uuid7())


def random_token(num_bytes: int = 32) -> str:
    """URL-safe random token (refresh tokens, email tokens, API secrets)."""
    if num_bytes < 16:
        raise ValueError("random_token requires at least 16 bytes of entropy")
    return secrets.token_urlsafe(num_bytes)


def random_hex(num_bytes: int = 32) -> str:
    """Random hex string (correlation ids, object key suffixes)."""
    return secrets.token_hex(num_bytes)


def random_crockford(length: int = CERTIFICATE_ID_RANDOM_LENGTH) -> str:
    """Random Crockford base32 string of exactly ``length`` characters."""
    if length < 1:
        raise ValueError("length must be positive")
    return "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(length))


def _checksum_char(body: str) -> str:
    """Position-weighted checksum over the Crockford body (typo/enumeration guard)."""
    total = 0
    for index, char in enumerate(body):
        value = CROCKFORD_ALPHABET.index(char)
        total += value * (index + 1)
    return CROCKFORD_ALPHABET[total % len(CROCKFORD_ALPHABET)]


def build_certificate_id(
    *,
    year: int | None = None,
    country: str = DEFAULT_COUNTRY_CODE,
    random_part: str | None = None,
) -> str:
    """Build an immutable public certificate identifier.

    Example: ``VK-KE-2026-7FQ2M9XB4KD1-Q``. ``random_part`` exists only so that
    tests can pin the random component; production callers leave it ``None``.
    """
    year = year or utcnow().year
    random_part = (random_part or random_crockford()).upper()
    if len(random_part) != CERTIFICATE_ID_RANDOM_LENGTH:
        raise ValueError("random_part must be 12 Crockford characters")
    if any(char not in CROCKFORD_ALPHABET for char in random_part):
        raise ValueError("random_part contains characters outside the Crockford alphabet")
    body = f"{CERTIFICATE_ID_PREFIX}-{country.upper()}-{year}-{random_part}"
    return f"{body}-{_checksum_char(random_part)}"


def normalize_certificate_id(value: str) -> str:
    """Normalise human input: uppercase, strip separators, map ambiguous glyphs.

    Crockford base32 treats ``I``/``L`` as ``1``, ``O`` as ``0`` and ``U`` as
    ``V`` so a certificate id that was read off a printed document still
    resolves. The mapping is applied to the random segment only - the country
    code legitimately contains letters such as ``IE``.
    """
    cleaned = value.strip().upper().replace(" ", "")
    segments = cleaned.split("-")
    if len(segments) == 5:
        for source, target in (("I", "1"), ("L", "1"), ("O", "0"), ("U", "V")):
            segments[3] = segments[3].replace(source, target)
        cleaned = "-".join(segments)
    return cleaned


def is_valid_certificate_id(value: str) -> bool:
    """Structurally validate a certificate id, including its checksum."""
    cleaned = normalize_certificate_id(value)
    parts = cleaned.split("-")
    if len(parts) != 5:
        return False
    prefix, country, year, body, checksum = parts
    if prefix != CERTIFICATE_ID_PREFIX or len(country) != 2 or not year.isdigit():
        return False
    if len(body) != CERTIFICATE_ID_RANDOM_LENGTH or len(checksum) != 1:
        return False
    if any(char not in CROCKFORD_ALPHABET for char in body + checksum):
        return False
    return _checksum_char(body) == checksum

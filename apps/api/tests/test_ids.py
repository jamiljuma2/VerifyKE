"""Unit tests for identifier primitives (section: no sequential ids)."""

from __future__ import annotations

import re
import uuid

import pytest

from verifyke.core.ids import (
    CERTIFICATE_ID_RANDOM_LENGTH,
    build_certificate_id,
    is_valid_certificate_id,
    new_uuid,
    normalize_certificate_id,
    random_token,
    utcnow,
)

CERT_ID_PATTERN = re.compile(r"^VK-KE-\d{4}-[0-9A-HJKMNP-TV-Z]{12}-[0-9A-HJKMNP-TV-Z]$")


def test_certificate_id_shape_and_checksum() -> None:
    value = build_certificate_id(year=2026)
    assert CERT_ID_PATTERN.match(value), value
    assert is_valid_certificate_id(value)


def test_certificate_ids_are_unique() -> None:
    ids = {build_certificate_id() for _ in range(500)}
    assert len(ids) == 500


def test_checksum_detects_tampering() -> None:
    value = build_certificate_id(year=2026, random_part="ABCDEFGHJKMN")
    assert is_valid_certificate_id(value)

    body, checksum = value.rsplit("-", 1)
    tampered_checksum = "0" if checksum != "0" else "1"
    assert not is_valid_certificate_id(f"{body}-{tampered_checksum}")

    # A single altered character in the random segment must also fail.
    tampered_body = body[:-1] + ("Z" if body[-1] != "Z" else "Y")
    assert not is_valid_certificate_id(f"{tampered_body}-{checksum}")


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        "VK-KE-2026-TOOSHORT-Q",
        "VK-KE-2026-ABCDEFGHJKMN",
        "XX-KE-2026-ABCDEFGHJKMN-Q",
        "VK-KE-26-ABCDEFGHJKMN-Q",
        "VK-KE-2026-ABCDEFGHJKM0-Q",
    ],
)
def test_invalid_certificate_ids_are_rejected(candidate: str) -> None:
    assert not is_valid_certificate_id(candidate)


def test_certificate_id_rejects_wrong_random_length() -> None:
    with pytest.raises(ValueError):
        build_certificate_id(random_part="ABC")
    with pytest.raises(ValueError):
        build_certificate_id(random_part="ABCDEFGHJKM1" * 2)


def test_normalisation_maps_ambiguous_characters() -> None:
    value = build_certificate_id(year=2026, random_part="0123456789AB")
    # Only the random segment is Crockford: read "0" as "O" and "1" as "I".
    body, checksum = value.rsplit("-", 1)
    spoken_body = body[:-CERTIFICATE_ID_RANDOM_LENGTH] + body[
        -CERTIFICATE_ID_RANDOM_LENGTH:
    ].replace("0", "O").replace("1", "I")
    spoken = f"{spoken_body}-{checksum}"
    assert spoken != value
    assert normalize_certificate_id(spoken) == value
    assert is_valid_certificate_id(spoken)


def test_uuid7_is_time_ordered() -> None:
    first = new_uuid()
    second = new_uuid()
    assert isinstance(first, uuid.UUID)
    assert first.version == 7
    assert first < second


def test_random_token_requires_sufficient_entropy() -> None:
    token = random_token()
    assert len(token) >= 40
    assert random_token() != token
    with pytest.raises(ValueError):
        random_token(8)


def test_utcnow_is_timezone_aware() -> None:
    assert utcnow().tzinfo is not None


def test_random_length_constant_is_documented() -> None:
    assert CERTIFICATE_ID_RANDOM_LENGTH == 12

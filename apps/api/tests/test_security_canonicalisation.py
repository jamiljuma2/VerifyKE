"""RFC 8785 canonicalisation guarantees."""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime

import pytest

from verifyke_security import (
    CanonicalisationError,
    canonical_digest,
    canonical_hash_hex,
    canonical_json,
    is_json_value,
)


def test_key_order_does_not_change_the_bytes() -> None:
    """Structurally equal payloads canonicalise to identical bytes."""
    first = canonical_json({"b": 2, "a": 1})
    second = canonical_json({"a": 1, "b": 2})
    assert first == second == b'{"a":1,"b":2}'


def test_nested_keys_are_sorted_and_whitespace_omitted() -> None:
    payload = {"z": [{"y": 1, "x": 2}], "a": " text "}
    assert canonical_json(payload) == b'{"a":" text ","z":[{"x":2,"y":1}]}'


def test_non_string_keys_are_rejected() -> None:
    with pytest.raises(CanonicalisationError, match="expected str"):
        canonical_json({1: "one"})  # type: ignore[dict-item]


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_numbers_are_rejected(value: float) -> None:
    with pytest.raises(CanonicalisationError, match="non-finite"):
        canonical_json(value)


def test_unsupported_types_report_their_path() -> None:
    with pytest.raises(CanonicalisationError, match=r"at \$\.when"):
        canonical_json({"when": object()})
    with pytest.raises(CanonicalisationError, match="datetime"):
        canonical_json({"at": datetime.now(UTC)})


def test_deeply_nested_payloads_are_rejected() -> None:
    payload: object = "leaf"
    for _ in range(40):
        payload = [payload]
    with pytest.raises(CanonicalisationError, match="nests deeper"):
        canonical_json(payload)  # type: ignore[arg-type]


def test_unicode_is_utf8_and_control_characters_are_escaped() -> None:
    assert canonical_json({"name": "Jámín Ûthman"}) == '{"name":"Jámín Ûthman"}'.encode()
    assert canonical_json({"t": "line\nbreak"}) == b'{"t":"line\\nbreak"}'


def test_json_escapes_match_the_spec() -> None:
    assert canonical_json({"q": 'quote " and \\ backslash'}) == (
        b'{"q":"quote \\" and \\\\ backslash"}'
    )


def test_digest_and_hash_helpers_agree_with_sha256_of_the_canonical_bytes() -> None:
    payload = {"a": 1}
    raw = canonical_json(payload)
    assert canonical_digest(payload) == hashlib.sha256(raw).digest()
    assert canonical_hash_hex(payload) == hashlib.sha256(raw).hexdigest()


def test_is_json_value_predicate() -> None:
    assert is_json_value({"ok": True, "list": [1, 2.5, None]})
    assert not is_json_value({"bad": math.nan})
    assert not is_json_value({1: "x"})
    assert not is_json_value({"when": datetime.now(UTC)})

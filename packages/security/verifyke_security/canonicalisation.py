"""RFC 8785 (JCS) canonical JSON.

A signature is only meaningful over *exactly* the bytes that were signed, so
VerifyKE canonicalises every signed payload with JCS: UTF-8, lexicographically
sorted object keys, no insignificant whitespace, and ECMAScript-compatible
number formatting. Two structurally equal payloads therefore produce identical
bytes regardless of how the dict was constructed or ordered.

Payloads are validated before canonicalisation so that a caller passing a
``datetime`` (or a NaN, or an ``int``-keyed dict) gets a precise, localisable
error instead of a library traceback or, worse, silently divergent bytes.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import rfc8785

from .errors import CanonicalisationError

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None

# Guard against pathological nesting (recursion limits, DoS via deep payloads).
_MAX_DEPTH = 32


def _validate_json(value: object, path: str = "$", depth: int = 0) -> None:
    """Ensure ``value`` contains only JSON-representable data."""
    if depth > _MAX_DEPTH:
        raise CanonicalisationError(f"payload nests deeper than {_MAX_DEPTH} levels at {path}")
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):  # bool is handled above; ints are fine for JCS
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalisationError(
                f"non-finite number at {path} cannot be represented in JSON"
            )
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalisationError(
                    f"object key at {path} is {type(key).__name__}, expected str"
                )
            _validate_json(item, f"{path}.{key}", depth + 1)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json(item, f"{path}[{index}]", depth + 1)
        return
    raise CanonicalisationError(f"unsupported type {type(value).__name__} at {path}")


def canonical_json(payload: JsonValue) -> bytes:
    """Return the RFC 8785 canonical UTF-8 encoding of ``payload``.

    Deterministic: equal payloads produce equal bytes, independent of key
    insertion order or whitespace.

    Raises :class:`~verifyke_security.errors.CanonicalisationError` when the
    payload is not pure JSON data.
    """
    _validate_json(payload)
    try:
        return rfc8785.dumps(payload)
    except Exception as exc:  # the backend must never leak its own errors
        raise CanonicalisationError("payload cannot be canonicalised as JSON") from exc


def canonical_digest(payload: JsonValue) -> bytes:
    """SHA-256 digest of the canonical encoding of ``payload``."""
    return hashlib.sha256(canonical_json(payload)).digest()


def canonical_hash_hex(payload: JsonValue) -> str:
    """Lowercase hex SHA-256 of the canonical encoding of ``payload``."""
    return canonical_digest(payload).hex()


def is_json_value(value: Any) -> bool:
    """Whether ``value`` would canonicalise successfully (no exception)."""
    try:
        canonical_json(value)
    except CanonicalisationError:
        return False
    return True

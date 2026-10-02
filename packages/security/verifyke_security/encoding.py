"""base64url helpers (RFC 4648 section 5, unpadded).

Signatures and other binary values are stored and transported as *unpadded*
base64url strings so they can sit directly in JSON, JWTs and database columns
without padding handling at every boundary.
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Final

from .errors import EncodingError

# Unpadded base64url alphabet: no '+', '/' or '='.
_B64U_PATTERN: Final = re.compile(r"^[A-Za-z0-9_-]*$")


def b64u_encode(data: bytes) -> str:
    """Encode bytes as an unpadded base64url string."""
    if not isinstance(data, bytes):
        raise EncodingError("b64u_encode expects bytes")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_decode(value: str) -> bytes:
    """Decode an unpadded base64url string back to bytes.

    Raises :class:`~verifyke_security.errors.EncodingError` for values that are
    not strings, contain characters outside the alphabet, or have an impossible
    length - never a raw ``binascii`` error.
    """
    if not isinstance(value, str):
        raise EncodingError("base64url value must be a string")
    if not _B64U_PATTERN.match(value):
        raise EncodingError("value contains characters outside the base64url alphabet")
    if len(value) % 4 == 1:
        raise EncodingError("value has an impossible base64url length")
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value.encode("ascii") + padding.encode("ascii"))
    except (binascii.Error, ValueError) as exc:  # pragma: no cover - defensive
        raise EncodingError("value is not valid base64url") from exc

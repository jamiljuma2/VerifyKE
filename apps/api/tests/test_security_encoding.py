"""base64url encoding helpers."""

from __future__ import annotations

import pytest

from verifyke_security import EncodingError, b64u_decode, b64u_encode


def test_round_trip() -> None:
    for raw in (b"", b"\x00", b"certificate bytes", bytes(range(256))):
        assert b64u_decode(b64u_encode(raw)) == raw


def test_encoding_is_unpadded_and_url_safe() -> None:
    encoded = b64u_encode(bytes(range(256)))
    assert "=" not in encoded
    assert "+" not in encoded
    assert "/" not in encoded
    # 0xFB 0xFF encode to characters that standard base64 maps to "+" and "/".
    assert b64u_encode(b"\xfb\xff") == "-_8"


def test_encode_requires_bytes() -> None:
    with pytest.raises(EncodingError, match="expects bytes"):
        b64u_encode("not-bytes")  # type: ignore[arg-type]


def test_decode_rejects_non_string_values() -> None:
    with pytest.raises(EncodingError, match="must be a string"):
        b64u_decode(123)  # type: ignore[arg-type]


def test_decode_rejects_foreign_alphabet() -> None:
    with pytest.raises(EncodingError, match="alphabet"):
        b64u_decode("abc+/def")
    with pytest.raises(EncodingError, match="alphabet"):
        b64u_decode("abc def")
    with pytest.raises(EncodingError, match="alphabet"):
        b64u_decode("abc=def")


def test_decode_rejects_impossible_length() -> None:
    with pytest.raises(EncodingError, match="impossible"):
        b64u_decode("A")

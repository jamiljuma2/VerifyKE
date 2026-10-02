"""Expected failures raised by :mod:`verifyke_security`.

Every failure the package raises on purpose derives from :class:`SecurityError`,
so callers can catch one type at a boundary while still distinguishing the
failure mode (and never receiving a leaked stack trace from deep crypto code).
"""

from __future__ import annotations


class SecurityError(Exception):
    """Base class for every expected failure raised by verifyke_security."""


class CanonicalisationError(SecurityError):
    """The payload cannot be represented as RFC 8785 canonical JSON."""


class EncodingError(SecurityError):
    """A value is not valid base64url (or is not a string at all)."""


class KeyMaterialError(SecurityError):
    """Key material is malformed: wrong length or not a valid Ed25519 key."""


class KeyWrapError(SecurityError):
    """A wrapped private key failed authentication.

    Typically the wrong master key, a mismatched AAD binding, or a tampered
    ciphertext. The original cause is chained via ``__cause__``.
    """


class InvalidKeyStatusError(SecurityError):
    """An operation is not permitted for the key's current status."""


class SignatureError(SecurityError):
    """A signature is missing, malformed, or does not verify."""

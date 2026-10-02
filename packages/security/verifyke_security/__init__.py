"""VerifyKE security primitives: canonicalisation, hashing, keys, signatures.

Public API::

    from verifyke_security import canonical_json, sign, verify
    from verifyke_security import create_key_version, signing_private_key

The package is intentionally dependency-light (``cryptography`` + ``rfc8785``)
and knows nothing about VerifyKE's configuration or database: callers pass key
material explicitly, which keeps every guarantee unit-testable in isolation.
"""

from __future__ import annotations

from .canonicalisation import (
    JsonValue,
    canonical_digest,
    canonical_hash_hex,
    canonical_json,
    is_json_value,
)
from .encoding import b64u_decode, b64u_encode
from .errors import (
    CanonicalisationError,
    EncodingError,
    InvalidKeyStatusError,
    KeyMaterialError,
    KeyWrapError,
    SecurityError,
    SignatureError,
)
from .hashing import (
    constant_time_equals,
    is_sha256_hex,
    sha256_digest,
    sha256_file,
    sha256_hex,
    sha256_stream,
)
from .keys import (
    ED25519_KEY_SIZE,
    MASTER_KEY_SIZE,
    WRAPPED_KEY_SIZE,
    KeyStatus,
    KeyVersion,
    create_key_version,
    generate_private_key,
    key_aad,
    public_key_from_private,
    require_master_key,
    signing_private_key,
    unwrap_private_key,
    wrap_private_key,
)
from .signing import (
    ALGORITHM,
    is_valid,
    public_key_matches,
    sign,
    sign_bytes,
    signature_for,
    verify,
    verify_bytes,
)

__version__ = "0.1.0"

__all__ = [
    "ALGORITHM",
    "ED25519_KEY_SIZE",
    "MASTER_KEY_SIZE",
    "WRAPPED_KEY_SIZE",
    "CanonicalisationError",
    "EncodingError",
    "InvalidKeyStatusError",
    "JsonValue",
    "KeyMaterialError",
    "KeyStatus",
    "KeyVersion",
    "KeyWrapError",
    "SecurityError",
    "SignatureError",
    "b64u_decode",
    "b64u_encode",
    "canonical_digest",
    "canonical_hash_hex",
    "canonical_json",
    "constant_time_equals",
    "create_key_version",
    "generate_private_key",
    "is_json_value",
    "is_sha256_hex",
    "is_valid",
    "key_aad",
    "public_key_from_private",
    "public_key_matches",
    "require_master_key",
    "sha256_digest",
    "sha256_file",
    "sha256_hex",
    "sha256_stream",
    "sign",
    "sign_bytes",
    "signature_for",
    "signing_private_key",
    "unwrap_private_key",
    "verify",
    "verify_bytes",
    "wrap_private_key",
]

# `verifyke_security`

Cryptographic primitives for VerifyKE (Phase 2 of the roadmap). Pure functions
over explicit key material: **no configuration, no database, no I/O** - the
API layer (`apps/api/verifyke`) supplies secrets and persistence.

| Module             | Responsibility                                                                                                                |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `canonicalisation` | RFC 8785 (JCS) canonical JSON: byte-exact serialisation for signing                                                           |
| `hashing`          | SHA-256 of bytes, streams and files; constant-time digest comparison                                                          |
| `keys`             | Ed25519 key generation, AES-256-GCM wrapping under the master key, `KeyVersion` status (`active` / `retired` / `compromised`) |
| `signing`          | Sign/verify canonical payloads; JSON-ready signature envelopes                                                                |
| `encoding`         | Unpadded base64url for storage and transport                                                                                  |
| `errors`           | One `SecurityError` hierarchy - never a leaked library traceback                                                              |

## Guarantees

- **Byte-exact signatures.** Every signature covers RFC 8785 canonical JSON,
  so key order and whitespace can never change what was signed.
- **Keys are wrapped, not stored.** Private keys exist in plaintext only while
  a signing operation runs; at rest they are AES-256-GCM ciphertext bound
  (via AAD) to their institution and version.
- **Status is enforced.** `retired` and `compromised` keys cannot sign;
  verification with a retired key still works because issued certificates
  reference the key version recorded at issuance.
- **Honest failures.** Anything expected (bad payload, wrong master key,
  tampered signature) raises a typed `SecurityError` subclass with a message
  safe to log; nothing else ever propagates from crypto internals.

## Quick usage

```python
from verifyke_security import create_key_version, key_aad, sign, signing_private_key, verify

aad = key_aad(institution_id="inst_01J...", version=1)
record, private_key = create_key_version(1, master_key, aad=aad)

envelope = sign({"certificate_number": "VK-KE-2026-..."}, private_key, key_id="v1")
verify({"certificate_number": "VK-KE-2026-..."}, envelope, record.public_key)

# later, in another process: unwrap again from the stored record
private_key = signing_private_key(record, master_key, aad=aad)
```

## Tests

Tests live with the API suite (`apps/api/tests/test_security_*.py`) and run in
the normal `make test` pass; the package is on pytest's `pythonpath`.

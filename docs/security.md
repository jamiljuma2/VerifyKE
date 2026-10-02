# VerifyKE security model

This document records the threat model and the controls that answer it. It is
written to be reviewable: each control names the attack it mitigates.

## 1. Assets

| Asset | Why it matters |
| --- | --- |
| Certificate records | The authority behind every "verified" result |
| Institution signing keys | Whoever holds them can forge certificates for that institution |
| Issued certificate PDFs | Source for content-hash comparison |
| Uploaded documents | Contain personal data; often the only copy a holder has |
| Personal data (holders, staff) | Kenya Data Protection Act obligations |
| Accounts and sessions | Precondition for issuing, revoking or bulk-exporting data |
| Audit log | Proves what happened; must not be rewritable |

## 2. Threat model

Adversaries we design against, in order of likelihood:

1. **Document forgers** - alter a certificate (name, grade, institution) or
   reprint a legitimate QR code onto a fake document.
2. **Credential attackers** - try to take over an issuer or admin account through
   password reuse, phishing or token theft.
3. **Malicious insiders** - a staff member exports or verifies data they have no
   business seeing.
4. **Opportunistic attackers** - automated scanners probing for common web flaws.
5. **Data harvesters** - mass-verify third parties' certificates to build profiles.

Explicit non-goals: defending against a compromised institution's own systems, or
against a state-level adversary with network interception of TLS.

## 3. Controls by layer

### 3.1 Identity and sessions

| Control | Mitigates |
| --- | --- |
| Argon2id password hashing (memory-hard) | Offline cracking after a database leak |
| zxcvbn strength scoring, 12-character minimum, breach-list check | Weak, reused passwords |
| TOTP MFA mandatory for `SUPER_ADMIN` and `INSTITUTION_ADMIN` | Phished or reused passwords |
| TOTP secrets encrypted at rest with the master key | Database leak defeating MFA |
| Account lockout with exponential backoff per account and per IP | Online brute force |
| Access token: 10-minute lifetime, `HttpOnly`, `Secure`, `SameSite=Strict` cookie | Token theft via XSS; CSRF |
| Refresh token: rotated on every use, stored as a SHA-256 hash, bound to a device fingerprint, reuse detection | Long-lived token theft and silent replay |
| Step-up re-authentication within 5 minutes for high-risk actions | Session hijack leading to key rotation or revocation |
| Session listing and remote revocation | Lost devices |

### 3.2 CSRF, XSS and transport

- Every state-changing request requires a double-submit token: the readable
  `vk_csrf` cookie must match the `X-CSRF-Token` header.
- Cookies are `SameSite=Strict`, so cross-site requests do not carry the session
  at all; the token is the second layer.
- The API sends `Content-Security-Policy: default-src 'none'`, `X-Frame-Options:
  DENY`, `Referrer-Policy: no-referrer` and HSTS in production.
- Untrusted content (QR payloads, OCR text, filenames) is rendered as text only -
  the web app forbids `dangerouslySetInnerHTML` and the PDF renderer escapes all
  field values.
- Nginx **overwrites** `X-Forwarded-For` rather than appending, so a client cannot
  spoof its address to escape per-IP rate limiting.

### 3.3 Authorisation and tenant isolation

Two independent layers, because a single missed filter is the most common way
tenant data leaks:

1. **Application**: every repository call is scoped to the caller's institution;
   role checks (`SUPER_ADMIN`, `INSTITUTION_ADMIN`, `INSTITUTION_ISSUER`,
   `VERIFIER`, `AUDITOR`) are enforced in the service layer, not the router.
2. **Database**: PostgreSQL row-level security policies keyed on
   `app.current_institution`, set per transaction with `set_config(..., true)`.
   The runtime role must not have `BYPASSRLS`.

Cross-tenant lookups return `404 NOT_FOUND`, never `403`, so the existence of
another institution's records is not disclosed.

### 3.4 Certificate integrity

- **Signing**: Ed25519 over an RFC 8785 (JSON Canonicalisation Scheme) payload
  containing the certificate's canonical fields. Canonicalisation is what makes the
  signature verifiable years later by a different implementation.
- **Key hierarchy**: an AES-256 master key (`VK_MASTER_KEY`, or AWS KMS when
  `VK_KEY_PROVIDER=aws_kms`) wraps per-institution Ed25519 keys. Only wrapped
  private keys are stored; plaintext keys exist only in memory during signing.
- **Key versions**: keys are versioned and never deleted. A retired or compromised
  key stays in the database so certificates issued under it remain verifiable;
  `compromised` marks the set of certificates that need re-issuance.
- **Content hash**: SHA-256 over the exact bytes of the issued PDF, stored with the
  certificate. Re-rendering a "matching" PDF does not produce the same bytes.
- **Copied QR codes**: the QR payload is a *claim*. VerifyKE always resolves it to a
  certificate and compares it with the document in hand - a QR that points at
  certificate A while the document is B yields `SUSPECT`.

### 3.5 File handling

- Size limit (`VK_UPLOAD_MAX_BYTES`), page limit and pixel limit prevent
  decompression bombs.
- MIME type is decided by magic bytes, never by the client-supplied header or the
  filename extension.
- Optional ClamAV scanning (`VK_MALWARE_SCANNER=clamav`, mandatory in production)
  before any parsing.
- Files are stored in private buckets with server-generated, short-lived signed URLs;
  object keys are random and never derived from user input.
- Uploaded documents are deleted on the retention schedule
  (`VK_PRIVACY_RETENTION_DAYS_UPLOADS`); the analysis result and audit entry remain.

### 3.6 Abuse and privacy

- Public lookups are rate-limited per IP; login attempts are limited per IP *and*
  per submitted account (hashed, so no email address is stored in Redis).
- Holder names are masked on public results
  (`VK_PUBLIC_VERIFICATION_MASKS_NAMES`); full details require an authenticated
  verifier or the holder's own access code.
- Verification events record who looked up what, for how long, which underpins the
  anomaly detection (bulk-lookup and impossible-travel alerts).
- Signup and verification require explicit consent for personal-data processing.

## 4. Audit and monitoring

The audit log is append-only (no `UPDATE`/`DELETE` grants) and records actor,
institution, action, target, IP, user agent, request id and timestamp. Security
events - repeated failed logins, MFA reset, key rotation, role change, unusual
verification volume, scanner fingerprints - raise alerts with severity levels.

Logs are structured JSON. A redaction processor strips anything named like a
secret (`password`, `token`, `private_key`, `mfa_secret`, `authorization`, ...)
before it is written, so a careless log statement cannot leak a credential.

## 5. Key management procedures

**Rotating an institution signing key** (no downtime, no invalidations):
1. Generate a new Ed25519 key wrapped with the current master key; mark it `active`.
2. Mark the previous version `retired`. Existing certificates keep verifying
   because verification selects the key version recorded on the certificate.
3. Re-sign nothing. Re-issuance is needed only for `compromised` keys.

**Rotating `VK_MASTER_KEY`**: decrypt every wrapped key with the old master key,
re-wrap with the new one, in a single verified batch, then retire the old key from
secret storage. Never overwrite the environment value before the re-wrap succeeds.

**Key compromise**: mark the version `compromised`, list affected certificates,
notify the institution, and re-issue from the new active key.

## 6. Incident response

1. **Detect** - monitoring alert or report.
2. **Contain** - revoke sessions for the affected accounts, rotate API keys,
   disable the compromised key version.
3. **Assess** - use the audit log and verification events to scope what was
   accessed.
4. **Notify** - affected institutions and, where personal data was exposed, the
   Office of the Data Protection Commissioner within the statutory window.
5. **Remediate and review** - fix, add a regression test, update this document.

## 7. Known accepted risks

| Risk | Rationale |
| --- | --- |
| Rate limiting fails open if Redis is down | Locks out no legitimate user; readiness reports degraded so traffic can be diverted. Revisit if Redis becomes redundant. |
| OCR misreads a photo of a genuine certificate | Reported as a failed/`NOT_APPLICABLE` check with a suggestion to re-upload, never as a verdict of forgery. |
| TOTP is phishable in real time | Accepted for now; WebAuthn/passkeys are the intended successor and the schema already stores per-credential metadata. |

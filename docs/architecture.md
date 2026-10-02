# VerifyKE architecture

## 1. Purpose and constraints

VerifyKE answers a single question with evidence: *is this document genuine and
unaltered?* The system is built for the Kenyan market first, which drives several
concrete constraints:

- **Low-end Android phones on metered, slow connections.** Pages must work without
  heavy client-side JavaScript; results are rendered on the server. Uploads are the
  only large payload, and they are bounded and compressed on the client.
- **Unreliable connectivity.** Verification of an uploaded document runs as a
  background job with a pollable status, so a dropped connection never loses work.
- **Institutions with varying IT capacity.** Institutions push certificates to
  VerifyKE through a documented API or by uploading a batch; they are not required
  to expose systems of their own.
- **Legal weight.** Every result must be explainable: which checks ran, what each
  found, and when. No opaque confidence score is ever shown.

## 2. Components

### 2.1 Web (`apps/web`)
Next.js 15 App Router. Public pages (verification, marketing) are server-rendered;
interactive parts are small client components. The web tier never holds an API
token: it forwards the caller's cookies to the API over the private network.

### 2.2 API (`apps/api`)
FastAPI, organised as:

```
verifyke/core/      infrastructure shared by every module
  config.py         validated settings (fails fast in production)
  logging.py        structlog + request/correlation context + secret redaction
  errors.py         AppError hierarchy and the single error envelope
  db.py             async engine, session factory, ORM mixins, RLS helper
  redis_client.py   shared async Redis client
  rate_limit.py     atomic Redis counters, per-IP and per-account
  middleware.py     request ids, security headers, blanket limits
  metrics.py        Prometheus instruments
  ids.py            UUIDv7 keys, Crockford certificate numbers, tokens
verifyke/modules/   feature modules: routers -> services -> repositories
verifyke/models/    SQLAlchemy models (metadata registered for Alembic)
```

A module owns its router, schemas, service layer and repository. Modules may call
another module's *service*; they never import another module's router or reach into
its tables directly.

### 2.3 Worker (`verifyke.worker`)
Celery workers execute document analysis, notification delivery, retention sweeps
and webhook retries. Jobs are idempotent and are identified by the entity they act
on, so a duplicated delivery cannot double-issue or double-revoke.

### 2.4 Data stores
| Store | Holds | Notes |
| --- | --- | --- |
| PostgreSQL | users, institutions, key versions, certificates, verification events, audit log | RLS for tenant scope; migrations only via Alembic |
| Redis | Celery broker/results, rate-limit counters, short TTL caches | never authoritative |
| Object storage | issued PDFs, uploaded documents, institution credentials | private buckets, server-generated signed URLs |

## 3. Request flows

### 3.1 Public verification by certificate number
1. Browser requests `/verify/VK-KE-2026-...`.
2. The web server component validates the identifier's *shape* (checksum) locally.
3. It calls `GET /api/v1/verify/{id}` on the internal network, forwarding cookies.
4. The API resolves the institution, loads the certificate, verifies the signature
   and hash, records a verification event, and returns a status with every check.
5. The web tier renders the result. No token is ever exposed to the browser.

### 3.2 Document upload
1. Client validates size and MIME type, then posts multipart to `/api/v1/verify/upload`.
2. API validates magic bytes, enforces limits, stores the object, and enqueues an
   analysis job - returning `202` with a verification id.
3. The worker extracts text, locates the certificate number, compares the document
   with the issuer record and analyses structure/metadata.
4. The client polls `/api/v1/verify/{verification_id}` until a final status is
   returned; the public page renders the same result view as the lookup path.

### 3.3 Certificate issuance (institution API)
1. Institution authenticates (session or API key) and posts the certificate payload.
2. The API validates the payload, selects the institution's active key version,
   canonicalises the data (RFC 8785) and signs it with Ed25519.
3. The PDF is rendered, hashed (SHA-256) and stored; the certificate row and audit
   entry are written in one transaction.
4. The QR code embedded in the PDF points at the verification URL for that
   certificate number.

## 4. Data model overview

```
institution ─┬─ institution_key (versioned, status: active | retired | compromised)
             ├─ user (roles, MFA enrolment, sessions)
             ├─ certificate_template (JSONB definition, versioned)
             └─ certificate ─┬─ document (issued PDF + hash)
                             ├─ verification_event (who checked it, when, how)
                             └─ audit_entry

verification_event ── document_upload ── analysis_result (checks + outcomes)
```

Conventions: UUIDv7 primary keys, `created_at`/`updated_at` maintained by the
database, soft deletes (`deleted_at`) instead of row removal, `citext` for emails
and certificate numbers, and JSONB only for genuinely schemaless data (template
definitions, evidence payloads).

## 5. Boundaries and failure behaviour

| Failure | Behaviour |
| --- | --- |
| Redis unavailable | Rate limiting degrades open with a loud warning; `/ready` reports unready so the load balancer removes the node. Verification keeps working for lookups. |
| PostgreSQL unavailable | Readiness fails, requests return `503` with a correlation id. No partial writes: every write is one transaction. |
| Object storage unavailable | Uploads are rejected (`503`); lookups still work because certificate records live in PostgreSQL. |
| OCR unavailable | Document analysis reports the check as `NOT_APPLICABLE` - it is never counted as a pass. |
| Worker backlog | Status stays `PENDING`; the client polls and sees progress rather than a false verdict. |

## 6. Extension points

- **New check types**: implement the check interface in
  `services/verification` and return `NOT_APPLICABLE` when it cannot run.
- **New countries**: certificate numbers carry a country segment; institution
  records store the issuing country and regulator.
- **New payment providers**: `VK_PAYMENT_PROVIDER` selects an adapter behind the
  same billing service interface.
- **Other clients (mobile app)**: consume `packages/shared-types` contracts and the
  same `/api/v1` surface.

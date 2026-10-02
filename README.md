# VerifyKE

**Trust Every Credential. Verify Every Certificate.**

VerifyKE verifies Kenyan (and, by design, international) academic certificates and
important documents. It answers one question with evidence: *is this document what
it claims to be?*

Unlike a QR-code checker, VerifyKE never trusts a single signal. A result is built
from independent checks - the issuing institution's authoritative record, the
digital signature on the certificate, a SHA-256 content hash, the destination the
QR code actually resolves to, document-structure analysis and revocation status -
and every check is reported to the user, including the ones that could not run.

---

## Contents

- [What is in this repository](#what-is-in-this-repository)
- [Architecture](#architecture)
- [Quick start (Docker)](#quick-start-docker)
- [Local development without Docker](#local-development-without-docker)
- [Configuration](#configuration)
- [Generating secrets](#generating-secrets)
- [Testing and quality gates](#testing-and-quality-gates)
- [Security model](#security-model)
- [Verification statuses](#verification-statuses)
- [Documentation](#documentation)

---

## What is in this repository

```
VerifyKE/
├── apps/
│   ├── api/                     FastAPI backend (Python 3.12)
│   │   ├── verifyke/
│   │   │   ├── core/            config, logging, errors, db, redis, rate limiting,
│   │   │   │                    middleware, metrics, identifiers
│   │   │   ├── modules/         feature modules (health today; auth, institutions,
│   │   │   │                    certificates, documents, verification, audit, ... to come)
│   │   │   └── models/          SQLAlchemy ORM models
│   │   ├── migrations/          Alembic migrations
│   │   └── tests/               pytest suite
│   └── web/                     Next.js 15 web app (App Router, TypeScript, Tailwind)
├── packages/
│   ├── shared-types/            TypeScript contracts shared with the API
│   ├── ui/                      Tailwind design-system primitives
│   ├── security/                (Phase 2) Ed25519 signing, canonicalisation, key hierarchy
│   └── document-processing/     (Phase 4) PDF/image analysis, OCR, tamper detection
├── services/
│   ├── verification/            (Phase 4) verification engine
│   └── notifications/           (Phase 5) email/SMS delivery
├── infrastructure/
│   ├── docker/                  Dockerfiles for the API/worker and web images
│   ├── nginx/                   single ingress (routes /api to FastAPI, / to Next.js)
│   ├── postgres/init/           extensions, least-privilege role, timeouts
│   └── monitoring/              Prometheus scrape configuration
├── scripts/dev/                 preflight checks and secret generation
├── docker-compose.yml           full local stack
└── .env.example                 every supported setting, documented
```

---

## Architecture

| Layer | Technology | Why |
| --- | --- | --- |
| API | FastAPI + Uvicorn (Python 3.12) | async I/O, typed contracts, OpenAPI by default |
| Validation | Pydantic v2 | one schema definition for runtime and docs |
| Database | PostgreSQL 16 | row-level security for tenant isolation, strong JSONB, extensions |
| Queue/cache | Redis 7 | Celery broker, rate limiting, short-lived caches - never the source of truth |
| Object storage | MinIO locally, S3 in production | documents/certificates stored outside the database, encrypted, private buckets |
| Web | Next.js 15 (App Router) | server components mean result pages render without client-side secrets |
| Ingress | Nginx | one origin (keeps cookies first-party), TLS termination, coarse rate limits |
| Background jobs | Celery worker + beat | document analysis, notifications, retention sweeps |

Requests flow: `client → Nginx → (web | api) → Postgres / Redis / S3`. The web app
reaches the API on the internal Docker network (`API_INTERNAL_URL`), never through
the public origin.

---

## Quick start (Docker)

Requirements: Docker with the Compose v2 plugin, 4 GB RAM, ports 3000/8000/8080
free.

```bash
cp .env.example .env          # then edit it
python scripts/dev/generate_secrets.py   # writes strong VK_SECRET_KEY / VK_MASTER_KEY

docker compose up -d --build

docker compose exec api alembic upgrade head
python scripts/dev/check_env.py          # confirms db, redis, storage, OCR
docker compose ps
```

| Service | URL |
| --- | --- |
| Web app | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Everything through Nginx | http://localhost:8080 |
| MinIO console | http://localhost:9001 |
| Mailpit (caught email) | http://localhost:8025 |
| Prometheus (opt-in) | `docker compose --profile observability up -d` → http://localhost:9090 |

Troubleshooting: if you already run PostgreSQL locally on 5432, either stop it or
set `POSTGRES_PORT=5433` in `.env` before starting the stack.

---

## Local development without Docker

Docker is the supported path, but the API runs directly against local services.

```bash
make venv install          # .venv with the API + dev dependencies
make env secrets           # .env with generated secrets
python scripts/dev/check_env.py   # PostgreSQL must accept the VK_DATABASE_URL

# apply schema (once a migration exists)
make migrate

make api                   # http://localhost:8000  (autoreload)
make web                   # http://localhost:3000  (npm workspace)
make test                  # pytest
make check                 # ruff + mypy + pytest, exactly what CI runs
```

Database roles: the application should connect as a role **without `BYPASSRLS`**,
otherwise row-level security silently stops protecting tenant data.
`infrastructure/postgres/init/01-extensions.sql` creates `verifyke_app` for this
purpose.

---

## Configuration

Every setting is an environment variable prefixed `VK_`, validated at startup by
`apps/api/verifyke/core/config.py`. `.env.example` documents all of them.

Two rules worth knowing:

1. **Production refuses to boot misconfigured.** A weak `VK_SECRET_KEY`, a
   non-`Secure` cookie, a plain-HTTP public URL, malware scanning disabled, or a
   missing `VK_MASTER_KEY` all abort startup with an explicit message.
2. **Secrets are never defaulted in.** There is no fallback secret: a missing
   critical value is an error, not a convenience.

---

## Generating secrets

```bash
python scripts/dev/generate_secrets.py            # update .env in place
python scripts/dev/generate_secrets.py --dry-run  # print only
python scripts/dev/generate_secrets.py --force    # rotate existing values
```

`VK_MASTER_KEY` is the root of the institution signing-key hierarchy. Rotating it
makes previously wrapped keys unreadable - rotate only before issuing certificates
or through the documented procedure in `docs/security.md`.

---

## Testing and quality gates

| Check | Command | Gate |
| --- | --- | --- |
| Lint + format | `make lint` | zero findings |
| Types | `make typecheck` | mypy clean, `tsc --noEmit` clean |
| Unit + API tests | `make test` | all green |
| Coverage | `pytest --cov=verifyke --cov-fail-under=80` | ≥ 80% (CI) |
| Migrations | `alembic upgrade head` | applies cleanly on a fresh database |
| Containers | CI image builds | both images build |
| Secrets | gitleaks | no committed secrets; `.env` is untracked |
| Dependencies | pip-audit | no known vulnerabilities |

---

## Security model

Short version - the full reasoning lives in `docs/security.md`.

- **Authentication**: Argon2id password hashing, TOTP multi-factor authentication
  required for administrative roles, account lockout with exponential backoff.
- **Sessions**: short-lived access tokens in `HttpOnly`, `Secure`, `SameSite=Strict`
  cookies; refresh tokens are rotated on every use, stored hashed, and bound to a
  device fingerprint so a stolen token is detectable.
- **CSRF**: a double-submit token (`vk_csrf` cookie + `X-CSRF-Token` header) on every
  state-changing request.
- **Tenant isolation**: institution scoping in the application *and* PostgreSQL
  row-level security keyed on a transaction-local setting, so a missed filter cannot
  leak another institution's data.
- **Certificates**: Ed25519 signatures over an RFC 8785 canonical JSON payload;
  SHA-256 content hashes over the exact bytes of the issued PDF; per-institution
  key versions so a rotated key never invalidates existing certificates.
- **Identifiers**: UUIDv7 primary keys (non-sequential, non-guessable) and
  checksum-protected public certificate numbers.
- **Auditing**: append-only audit log plus security-event monitoring
  (impossible travel, unusual verification volume, scanner fingerprints).
- **Untrusted input**: uploaded files are size- and magic-byte-validated, scanned
  when `VK_MALWARE_SCANNER=clamav`, and parsed with limits on pages and pixels.
  QR codes and OCR text are treated as *claims to check*, never as facts.

---

## Verification statuses

| Status | Meaning |
| --- | --- |
| `VERIFIED` | Issuer record, signature and content checks all passed. |
| `SUSPECT` | A concern was detected (e.g. repaired PDF, QR pointing elsewhere). Human review recommended. |
| `FAILED` | A decisive check failed: the document does not match the issuer's record. |
| `NOT_FOUND` | No certificate matches the identifier or document. |
| `REVOKED` | Validly issued, then withdrawn by the institution. |
| `EXPIRED` | Past its validity date. |
| `PENDING` | Still processing (document analysis in progress). |

A "copied QR code" - a legitimate QR image reprinted onto a different certificate -
is detected as `SUSPECT`: the QR resolves to certificate *A* while the document in
hand is *B*, which no single-signal checker can notice.

---

## Documentation

| Document | Contents |
| --- | --- |
| `docs/architecture.md` | components, request flows, module boundaries, data model overview |
| `docs/security.md` | threat model, controls, key management, incident response |
| `docs/database.md` | schema conventions, migration workflow, row-level security |
| `docs/deployment.md` | production topology, TLS, backups, scaling, rollout |

---

## Licence

Proprietary. © VerifyKE.

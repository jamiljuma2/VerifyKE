# VerifyKE API

FastAPI backend for VerifyKE. Run it from this directory:

```bash
uvicorn verifyke.main:app --reload --port 8000     # development
pytest -q                                          # test suite
ruff check . && ruff format --check .              # lint / format
alembic upgrade head                               # apply migrations
alembic revision --autogenerate -m "add x"         # create a migration
```

## Layout

```
verifyke/
  main.py            application factory, middleware wiring, lifespan
  observability.py   optional Sentry integration (VK_SENTRY_DSN)
  core/
    config.py        validated settings; refuses to boot a misconfigured production
    logging.py       structlog setup, request context, secret redaction
    errors.py        AppError hierarchy + the single client-facing error envelope
    db.py            async engine/session, ORM mixins, RLS tenant context
    redis_client.py  shared async Redis client
    rate_limit.py    atomic Redis counters (per IP and per account)
    middleware.py    request ids, security headers, blanket rate limiting
    metrics.py       Prometheus instruments
    ids.py           UUIDv7 keys, Crockford certificate numbers, tokens
  modules/           feature modules (routers -> services -> repositories)
  models/            SQLAlchemy models registered for Alembic autogenerate
tests/               pytest suite (unit + API, integration marked separately)
migrations/          Alembic environment and versions
```

## Endpoints available today

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness (no dependencies) |
| GET | `/ready` | readiness: PostgreSQL, Redis |
| GET | `/version` | service version and environment |
| GET | `/metrics` | Prometheus exposition (internal only) |
| GET | `/docs` | OpenAPI documentation |

Feature modules (`auth`, `institutions`, `certificates`, `verification`, `audit`,
`security`, `billing`) are registered by `register_api_routers` as they are built;
until then the service starts without them and logs `router_not_installed`.

## Conventions

- Routers stay thin: validation and authorisation happen in the service layer.
- Every query that touches tenant data is scoped to the caller's institution in the
  repository *and* protected by PostgreSQL RLS.
- Errors are raised as `AppError` subclasses, never as bare `HTTPException`, so the
  response envelope and status mapping stay consistent.
- Nothing sensitive is ever bound to a log context; see `SENSITIVE_KEYS`.

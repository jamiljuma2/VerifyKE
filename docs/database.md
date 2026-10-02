# Database conventions and migrations

## 1. Principles

- **PostgreSQL is the source of truth.** Redis and object storage are helpers;
  nothing is considered issued, verified or revoked until the row is committed.
- **One migration tool.** Alembic only. No manual `CREATE TABLE` in an environment
  that matters: `infrastructure/postgres/init/` is limited to extensions, the
  least-privilege role and timeouts.
- **Migrations are reviewed like code.** Autogenerate is a starting point; a human
  checks that a column rename did not become a drop-and-add.
- **Every schema change is forward-only in production.** Downgrades exist for
  development convenience, not as a rollback plan: a destructive change is
  deployed in stages (add new column, backfill, switch reads, drop after a release).

## 2. Conventions

| Concern | Convention |
| --- | --- |
| Primary keys | `uuid` (UUIDv7), generated in the application, time-ordered for index locality |
| Timestamps | `created_at` / `updated_at` (`timestamptz`, database defaults, UTC) |
| Deletion | `deleted_at` soft delete; audit and verification records are never deleted |
| Text uniqueness | `citext` for emails, certificate numbers and institution slugs |
| Enums | PostgreSQL native enums for closed sets (status, role); never free text |
| Money | `numeric(12,2)` plus an explicit currency column; never floating point |
| JSON | `jsonb` only for genuinely schemaless data (template definition, evidence payload) |
| Constraint names | Deterministic via `MetaData(naming_convention=...)` in `verifyke/core/db.py` |
| Indexes | Explicit, named after the columns they cover; partial indexes for active rows |

## 3. Row-level security (tenant isolation)

The application scopes every query by institution, and the database enforces it
again so that a missed filter cannot leak data:

```sql
ALTER TABLE certificate ENABLE ROW LEVEL SECURITY;
ALTER TABLE certificate FORCE ROW LEVEL SECURITY;

CREATE POLICY certificate_tenant_isolation ON certificate
  USING (institution_id = NULLIF(current_setting('app.current_institution', true), '')::uuid)
  WITH CHECK (institution_id = NULLIF(current_setting('app.current_institution', true), '')::uuid);

GRANT SELECT, INSERT, UPDATE, DELETE ON certificate TO verifyke_app;
REVOKE ALL ON certificate FROM PUBLIC;
```

The application sets the value per transaction:

```python
await set_tenant_context(session, institution_id)   # verifyke/core/db.py
```

`set_config(..., is_local => true)` scopes the setting to the transaction, so a
pooled connection cannot carry one tenant's context into another request.

Platform-level operations (public verification, super-admin reporting) run with an
empty setting and are covered by permissive policies for the read-only paths they
need - **not** by disabling RLS.

> The runtime role must not have `BYPASSRLS` or be the table owner, otherwise
> every policy above is silently ignored.

## 4. Migration workflow

```bash
make migration m="add certificate revocation fields"   # autogenerate
# review, edit, remove noise
make migrate                                           # apply locally
```

Checklist for a migration under review:

1. Does it take an `ACCESS EXCLUSIVE` lock on a large table? If so, split it
   (add nullable column, backfill in batches, then set `NOT NULL`).
2. Is it reversible without data loss? If not, say so in the docstring.
3. Are new tables granted to the runtime role and protected by RLS?
4. Do indexes get created with `CONCURRENTLY` where the table is already large?
   (This requires `op.execute` outside a transaction: `alembic` runs each migration
   in its own transaction with `transaction_per_migration=True`.)

## 5. Data retention and deletion

| Data | Retention | Mechanism |
| --- | --- | --- |
| Uploaded documents | `VK_PRIVACY_RETENTION_DAYS_UPLOADS` (30 days default) | Celery beat sweep deletes objects, keeps the analysis result |
| Issued certificate PDFs | Life of the certificate + 7 years | Deleted only by an authorised retention job |
| Verification events | 7 years | Aggregates retained for reporting; individual events expire per policy |
| Audit log | `VK_PRIVACY_RETENTION_DAYS_AUDIT_LOGS` (≈7 years) | Append-only; no UPDATE/DELETE grants |

A subject access request is served by an export job that produces every record
linked to a verified identifier; erasure is implemented as pseudonymisation where
the audit obligation forbids outright deletion, and the reason is recorded.

## 6. Backups and recovery

- Nightly `pg_dump --format=custom` plus continuous WAL archiving for
  point-in-time recovery; both are encrypted before leaving the host.
- Restores are rehearsed monthly into a scratch database; a backup that has never
  been restored is treated as unverified.
- Object storage is replicated independently; the database stores object *keys*,
  never the documents themselves.
- Verification of integrity after restore: certificate content hashes are
  recomputed for a random sample, which detects silent storage corruption.

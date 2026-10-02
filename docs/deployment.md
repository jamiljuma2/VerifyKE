# Deployment

## 1. Topology

```
                    ┌──────────────┐
Internet ──TLS────► │    Nginx     │  one origin: / → web, /api → api
                    └──────┬───────┘
                           │ private network
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐       ┌──────────┐      ┌───────────┐
   │  web    │       │   api    │◄────►│  worker   │  Celery worker + beat
   └─────────┘       └────┬─────┘      └───────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   ┌─────────┐      ┌──────────┐     ┌────────────┐
   │Postgres │      │  Redis   │     │ S3 / MinIO │
   └─────────┘      └──────────┘     └────────────┘
```

Only Nginx is published. PostgreSQL, Redis and object storage must never be
reachable from the internet; a managed database with a private endpoint is
preferred over a self-hosted instance.

## 2. Prerequisites

- Docker Engine with the Compose v2 plugin (`docker compose version`)
- A domain with DNS pointing at the host, and TLS certificates (for example
  Let's Encrypt via certbot or a managed load balancer)
- Secrets in a secret manager (AWS Secrets Manager, SSM Parameter Store, Vault) -
  not in a `.env` file on disk
- Object storage bucket(s) with public access blocked and server-side encryption on
- Mail sending domain configured (SPF, DKIM, DMARC) - verification emails land in
  the holders' inboxes or nowhere

## 3. First deployment

```bash
# 1. Environment
git clone <repo> /srv/verifyke && cd /srv/verifyke
cp .env.example .env
#   set VK_APP_ENV=production, https URLs, VK_COOKIE_SECURE=true,
#   VK_MALWARE_SCANNER=clamav, VK_KEY_PROVIDER=aws_kms (or a real VK_MASTER_KEY),
#   a unique VK_SECRET_KEY, real SMTP and S3 credentials

# 2. Preflight: the API refuses to boot a misconfigured production
python scripts/dev/check_env.py

# 3. Bring the stack up
docker compose up -d --build

# 4. Apply migrations (the api service also does this on start)
docker compose exec api alembic upgrade head

# 5. Prove it is healthy
curl -fsS https://verifyke.example/health
curl -fsS https://verifyke.example/ready
```

`/ready` must return `"status": "ok"`. If it returns `503`, the response body names
the failing dependency; do not put the instance behind the load balancer until it
is green.

## 4. TLS and Nginx

TLS terminates at Nginx (or at a managed load balancer in front of it). When
terminating at Nginx, mount the certificate and enable the `https` server block in
`infrastructure/nginx/conf.d/default.conf`, then:

- set `VK_COOKIE_SECURE=true` (already enforced in production by the settings
  validator) and `VK_COOKIE_SAMESITE=strict`;
- keep `Strict-Transport-Security` enabled (the API sets it in production);
- redirect `http://` to `https://` at the ingress;
- keep `/metrics` denied publicly - it is internal-only by design.

## 5. Configuration notes for production

| Setting | Value | Why |
| --- | --- | --- |
| `VK_APP_ENV` | `production` | Enables JSON logs, HSTS, and the strict config validator |
| `VK_DEBUG` | `false` | Required; the validator rejects `true` |
| `VK_COOKIE_SECURE` | `true` | Required |
| `VK_KEY_PROVIDER` | `aws_kms` (or `local` + strong `VK_MASTER_KEY`) | Signing keys must be wrapped by a managed root |
| `VK_MALWARE_SCANNER` | `clamav` | Required; the validator rejects `none` |
| `VK_STORAGE_BACKEND` | `s3` | Local filesystem storage does not survive a container replacement |
| `VK_MAIL_BACKEND` | `smtp` | `console` silently discards holder notifications |
| `VK_SENTRY_DSN` | set | Error tracking with PII disabled |
| `VK_LOG_JSON` | `true` | Machine-readable logs for the aggregator |
| `VK_DATABASE_URL` | role **without** `BYPASSRLS` | Otherwise row-level security is decorative |

## 6. Scaling

| Component | Scale by | Notes |
| --- | --- | --- |
| `api` | replicas | Stateless. Migrations run on start under an advisory lock, so replicas may boot together. |
| `worker` | replicas and `--concurrency` | CPU-bound (OCR/PDF). Keep `--max-tasks-per-child` so a leaking parser cannot accumulate. |
| `beat` | **exactly one** | Two schedulers double-fire every periodic job. |
| `postgres` | vertical first, then read replicas | Reporting reads can go to a replica; all writes stay on the primary. |
| `redis` | vertical | Rate-limit counters and the Celery queue share one instance only in small deployments. |
| `web` | replicas | Stateless Next.js standalone server. |

Celery queues should be split (`documents`, `notifications`, `default`) once
volume justifies it, so a slow OCR backlog cannot delay password-reset emails.

## 7. Backups and disaster recovery

- **Database**: nightly logical dump + WAL archiving for point-in-time recovery;
  encrypted before leaving the host; restore rehearsed monthly.
- **Object storage**: versioning plus cross-region replication. Issued certificate
  PDFs are irreplaceable: without them, hash comparison degrades to `NOT_APPLICABLE`.
- **Secrets**: backed up in the secret manager with a documented recovery contact.
  Losing the master key means every wrapped institution key is unreadable.
- **Targets**: RPO 15 minutes, RTO 4 hours. Document the last rehearsal date.

## 8. Rollout and rollback

```bash
git pull
python scripts/dev/check_env.py         # config sanity
docker compose build
docker compose up -d --no-deps api worker web   # replace, not restart-en-masse
docker compose exec api alembic upgrade head    # after the new image is healthy
```

Rollback: redeploy the previous image tag. Because migrations are forward-only in
production, a rollback that requires a schema change is instead finished forward
with a follow-up migration. Keep the previous image tagged and available.

Smoke test after every deploy:

```bash
curl -fsS https://verifyke.example/health
curl -fsS https://verifyke.example/ready
curl -fsS "https://verifyke.example/api/v1/verify/VK-KE-2026-XXXXXXXXXXXX-X"   # expect a structured result
```

## 9. Monitoring and alerting

- Scrape `/metrics` from the private network (`infrastructure/monitoring/prometheus.yml`).
- Alert on: `/ready` failing, HTTP 5xx rate, p95 latency above target, rate-limit
  rejections spiking (an attack or a stuck client), worker queue depth growing,
  failed logins per account, and `verifyke_security_events_total` by severity.
- Ship structured logs to a searchable store. Every log line carries `request_id`,
  which is also returned to the client in the error envelope - that pairing is what
  makes support requests answerable.

## 10. Operational runbook (short form)

| Symptom | First checks |
| --- | --- |
| Verification returns `PENDING` forever | `docker compose logs -f worker`; queue depth; Redis health |
| `/ready` degraded, database error | database reachable? connection pool exhausted? long-running query holding locks? |
| Rate limiting warning in logs | Redis down - fix Redis; traffic is currently limiter-free |
| Certificates fail signature checks after a deploy | was a key version retired without re-issuing? was `VK_MASTER_KEY` rotated without re-wrapping? |
| Emails not delivered | `VK_MAIL_BACKEND=smtp`? SPF/DKIM? provider reputation? |

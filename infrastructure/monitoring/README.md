# Monitoring

`prometheus.yml` scrapes the API's `/metrics` endpoint. The endpoint is exported
only on the internal Docker network and is explicitly denied by the public Nginx
server block, so metrics are never reachable from the internet.

## Metrics exposed by VerifyKE

| Metric | Type | Purpose |
| --- | --- | --- |
| `verifyke_http_requests_total` | counter | Traffic by route/status |
| `verifyke_http_request_duration_seconds` | histogram | Latency (p50/p95/p99) |
| `verifyke_verification_requests_total` | counter | Verification volume by outcome |
| `verifyke_verification_duration_seconds` | histogram | Verification latency |
| `verifyke_auth_events_total` | counter | Login/MFA/lockout events |
| `verifyke_security_events_total` | counter | Security events by severity |
| `verifyke_rate_limit_hits_total` | counter | Rejected requests by limiter scope |
| `verifyke_document_processing_total` | counter | OCR/analysis outcomes |
| `verifyke_queue_jobs_in_flight` | gauge | Background job concurrency |

Labels are restricted to route *templates* (for example
`/api/v1/certificates/{certificate_id}`), never raw paths, so cardinality stays
bounded and certificate identifiers never enter the metrics store.

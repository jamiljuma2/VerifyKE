"""System endpoint tests: liveness, readiness, version, metrics, banner."""

from __future__ import annotations

from httpx import AsyncClient


async def test_liveness_probe_has_no_dependencies(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "verifyke-api"
    assert body["uptime_seconds"] >= 0


async def test_version_endpoint_reports_environment(client: AsyncClient) -> None:
    response = await client.get("/version")
    assert response.status_code == 200
    assert response.json()["environment"] == "test"


async def test_readiness_reports_dependency_state(client: AsyncClient) -> None:
    """Readiness always answers with a per-dependency breakdown.

    Without live PostgreSQL/Redis the endpoint must report 503 (never a 500 with
    a stack trace), which is what the load balancer needs to see.
    """
    response = await client.get("/ready")
    assert response.status_code in (200, 503)
    body = response.json()
    assert set(body["dependencies"]) == {"database", "redis"}
    if response.status_code == 503:
        assert body["status"] == "degraded"


async def test_metrics_endpoint_exposes_prometheus_payload(client: AsyncClient) -> None:
    await client.get("/health")
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "verifyke_http_requests_total" in response.text


async def test_banner_does_not_disclose_configuration(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "verifyke-api"
    assert "secret" not in response.text.lower()
    assert "localhost" not in response.text


async def test_versioned_health_alias(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_security_headers_are_present(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


async def test_request_id_is_echoed_and_generated(client: AsyncClient) -> None:
    generated = await client.get("/health")
    assert len(generated.headers["x-request-id"]) == 32

    supplied = await client.get("/health", headers={"X-Request-ID": "client-supplied-id-123456"})
    assert supplied.headers["x-request-id"] == "client-supplied-id-123456"
    assert supplied.headers["x-correlation-id"] == "client-supplied-id-123456"


async def test_openapi_document_is_available(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"].startswith("VerifyKE")
    assert "/health" in schema["paths"]

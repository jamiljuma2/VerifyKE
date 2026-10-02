"""Error envelope tests - clients always get a stable, non-leaking shape."""

from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from verifyke.core.errors import ConflictError


class EchoPayload(BaseModel):
    name: str
    count: int


def _register_probe_routes(app: FastAPI) -> None:
    @app.post("/_probe/echo", include_in_schema=False)
    async def echo(payload: EchoPayload) -> EchoPayload:  # pragma: no cover - trivial
        return payload

    @app.get("/_probe/conflict", include_in_schema=False)
    async def conflict() -> None:
        raise ConflictError(
            "Certificate already revoked.", details={"certificate_id": "VK-KE-2026-ABCDEFGHJKMN-Q"}
        )

    @app.get("/_probe/boom", include_in_schema=False)
    async def boom() -> None:
        raise RuntimeError("internal detail that must never leak: postgres://user:pw@host")


async def test_not_found_uses_envelope(client: AsyncClient, app: FastAPI) -> None:
    response = await client.get("/definitely/not/here")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert "request_id" in error


async def test_validation_error_details_are_structured(client: AsyncClient, app: FastAPI) -> None:
    _register_probe_routes(app)
    response = await client.post("/_probe/echo", json={"name": 5})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]
    assert {"location", "message", "type"} == set(error["details"][0])


async def test_application_error_maps_to_status_and_code(client: AsyncClient, app: FastAPI) -> None:
    _register_probe_routes(app)
    response = await client.get("/_probe/conflict")
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "CONFLICT"
    assert error["message"] == "Certificate already revoked."
    assert error["details"]["certificate_id"] == "VK-KE-2026-ABCDEFGHJKMN-Q"


async def test_unhandled_exception_is_opaque(app: FastAPI) -> None:
    _register_probe_routes(app)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as raw_client:
        response = await raw_client.get("/_probe/boom")
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert "postgres" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text


async def test_method_not_allowed_uses_envelope(client: AsyncClient) -> None:
    response = await client.delete("/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"

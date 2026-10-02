"""Consistent, non-leaking API errors.

Every error surfaced to a client uses the documented envelope::

    {"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}

Internal details (stack traces, SQL, secrets) are never included. Unexpected
exceptions are logged with full context and reported as ``INTERNAL_ERROR``.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from verifyke.core.logging import get_logger, get_request_id

logger = get_logger(__name__)

# Starlette renamed these status constants; support both without emitting
# deprecation warnings on newer versions.
HTTP_422_UNPROCESSABLE = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
HTTP_413_TOO_LARGE = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)


class AppError(Exception):
    """Base class for expected, client-safe application errors."""

    code = "INTERNAL_ERROR"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any = None,
        code: str | None = None,
        http_status: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        if message:
            self.message = message
        self.details = details
        if code:
            self.code = code
        if http_status:
            self.http_status = http_status
        self.headers = headers or {}
        super().__init__(self.message)


class ValidationError(AppError):
    code = "VALIDATION_ERROR"
    http_status = HTTP_422_UNPROCESSABLE
    message = "The request payload failed validation."


class AuthenticationError(AppError):
    code = "AUTHENTICATION_REQUIRED"
    http_status = status.HTTP_401_UNAUTHORIZED
    message = "Authentication is required."


class InvalidCredentialsError(AppError):
    code = "INVALID_CREDENTIALS"
    http_status = status.HTTP_401_UNAUTHORIZED
    message = "The provided credentials are incorrect."


class AccountLockedError(AppError):
    code = "ACCOUNT_LOCKED"
    http_status = status.HTTP_423_LOCKED
    message = "This account is temporarily locked. Try again later."


class MfaRequiredError(AppError):
    code = "MFA_REQUIRED"
    http_status = status.HTTP_401_UNAUTHORIZED
    message = "Multi-factor authentication is required to continue."


class ReauthenticationRequiredError(AppError):
    code = "REAUTHENTICATION_REQUIRED"
    http_status = status.HTTP_401_UNAUTHORIZED
    message = "This action requires you to re-authenticate."


class PermissionDeniedError(AppError):
    code = "PERMISSION_DENIED"
    http_status = status.HTTP_403_FORBIDDEN
    message = "You do not have permission to perform this action."


class CsrfError(AppError):
    code = "CSRF_VALIDATION_FAILED"
    http_status = status.HTTP_403_FORBIDDEN
    message = "The request could not be verified. Refresh the page and try again."


class NotFoundError(AppError):
    """Also used deliberately for cross-tenant access, so that the existence of
    another tenant's resource is never disclosed (prevents IDOR enumeration)."""

    code = "NOT_FOUND"
    http_status = status.HTTP_404_NOT_FOUND
    message = "The requested resource was not found."


class ConflictError(AppError):
    code = "CONFLICT"
    http_status = status.HTTP_409_CONFLICT
    message = "The resource already exists or is in a conflicting state."


class GoneError(AppError):
    code = "RESOURCE_GONE"
    http_status = status.HTTP_410_GONE
    message = "The requested resource is no longer available."


class PayloadTooLargeError(AppError):
    code = "PAYLOAD_TOO_LARGE"
    http_status = HTTP_413_TOO_LARGE
    message = "The uploaded payload exceeds the permitted size."


class UnsupportedMediaTypeError(AppError):
    code = "UNSUPPORTED_MEDIA_TYPE"
    http_status = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    message = "The uploaded file type is not supported."


class RateLimitError(AppError):
    code = "RATE_LIMITED"
    http_status = status.HTTP_429_TOO_MANY_REQUESTS
    message = "Too many requests. Please slow down and try again shortly."


class ServiceUnavailableError(AppError):
    code = "SERVICE_UNAVAILABLE"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE
    message = "A required dependency is temporarily unavailable."


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
def error_envelope(code: str, message: str, details: Any = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    request_id = get_request_id()
    if request_id:
        payload["request_id"] = request_id
    return {"error": payload}


async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    if exc.http_status >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error("application_error", code=exc.code, message=exc.message, exc_info=exc)
    return JSONResponse(
        status_code=exc.http_status,
        content=error_envelope(exc.code, exc.message, exc.details),
        headers=exc.headers or None,
    )


async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert FastAPI validation errors into a stable, non-leaking shape."""
    details = [
        {
            "location": ".".join(str(part) for part in error.get("loc", [])),
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=ValidationError.http_status,
        content=error_envelope(ValidationError.code, ValidationError.message, details),
    )


async def _http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code_map = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "AUTHENTICATION_REQUIRED",
        status.HTTP_403_FORBIDDEN: "PERMISSION_DENIED",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_409_CONFLICT: "CONFLICT",
        status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return JSONResponse(status_code=exc.status_code, content=error_envelope(code, message))


async def _unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    # Log everything internally; reveal nothing externally.
    logger.error("unhandled_exception", exc_type=type(exc).__name__, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_envelope("INTERNAL_ERROR", "An unexpected error occurred."),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach VerifyKE's error handlers to the FastAPI application."""
    app.add_exception_handler(AppError, _app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_exception_handler)

"""Logging safety: secrets never reach the log stream."""

from __future__ import annotations

from verifyke.core.logging import (
    REDACTED,
    SENSITIVE_KEYS,
    _redact,
    bind_actor,
    clear_context,
    get_correlation_id,
    get_request_id,
    set_correlation_id,
    set_request_id,
)


def _process(event_dict: dict) -> dict:
    """Apply the redaction processor the way structlog would."""
    return _redact(None, "info", dict(event_dict))


def test_sensitive_keys_are_redacted() -> None:
    payload = _process(
        {
            "event": "login_attempt",
            "email": "holder@example.ke",
            "password": "Correct-Horse-Battery-Staple",
            "access_token": "eyJhbGciOi...",
            "Private_Key": "-----BEGIN PRIVATE KEY-----",
        }
    )
    assert payload["password"] == REDACTED
    assert payload["access_token"] == REDACTED
    assert payload["Private_Key"] == REDACTED
    assert payload["email"] == "holder@example.ke"  # operational, not secret


def test_expected_secret_field_names_are_covered() -> None:
    for name in ("password", "refresh_token", "mfa_secret", "secret_key", "authorization"):
        assert name in SENSITIVE_KEYS


def test_request_context_round_trip() -> None:
    clear_context()
    assert get_request_id() is None
    set_request_id("req-123")
    set_correlation_id("corr-456")
    assert get_request_id() == "req-123"
    assert get_correlation_id() == "corr-456"
    clear_context()
    assert get_request_id() is None


def test_actor_binding_is_context_scoped() -> None:
    clear_context()
    bind_actor(actor_id="user-1", institution_id="inst-1")
    assert get_request_id() is None  # unaffected by actor binding
    clear_context()

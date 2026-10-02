"""Configuration validation tests (fail-safe production boot)."""

from __future__ import annotations

import base64
import os

import pytest
from pydantic import ValidationError as PydanticValidationError

from verifyke.core.config import DEV_SECRET_PLACEHOLDER, Settings

PRODUCTION_BASE = {
    "app_env": "production",
    "secret_key": "a-production-grade-secret-value-0123456789abcdef",
    "cookie_secure": True,
    "web_base_url": "https://verifyke.example",
    "api_base_url": "https://api.verifyke.example",
    "malware_scanner": "clamav",
    "master_key": base64.urlsafe_b64encode(os.urandom(32)).decode(),
}


def test_development_defaults_are_permissive() -> None:
    settings = Settings(app_env="development")
    assert settings.is_production is False
    assert settings.json_logs is False


def test_production_accepts_hardened_configuration() -> None:
    # `log_json=None` explicitly selects "auto: JSON in production", so the test
    # does not depend on whatever VK_LOG_JSON the developer's .env happens to hold.
    settings = Settings(**PRODUCTION_BASE, log_json=None)
    assert settings.is_production is True
    assert settings.json_logs is True
    assert settings.cors_origin_list == ["http://localhost:3000"]


def test_explicit_log_format_overrides_the_production_default() -> None:
    settings = Settings(**PRODUCTION_BASE, log_json=False)
    assert settings.json_logs is False


def test_production_rejects_default_secret() -> None:
    with pytest.raises(PydanticValidationError) as excinfo:
        Settings(**{**PRODUCTION_BASE, "secret_key": DEV_SECRET_PLACEHOLDER})
    assert "VK_SECRET_KEY" in str(excinfo.value)


def test_production_rejects_short_secret() -> None:
    with pytest.raises(PydanticValidationError) as excinfo:
        Settings(**{**PRODUCTION_BASE, "secret_key": "too-short"})
    assert "at least 32 characters" in str(excinfo.value)


def test_production_rejects_insecure_cookies() -> None:
    with pytest.raises(PydanticValidationError) as excinfo:
        Settings(**{**PRODUCTION_BASE, "cookie_secure": False})
    assert "VK_COOKIE_SECURE" in str(excinfo.value)


def test_production_rejects_plain_http_public_urls() -> None:
    with pytest.raises(PydanticValidationError) as excinfo:
        Settings(**{**PRODUCTION_BASE, "web_base_url": "http://verifyke.example"})
    assert "https" in str(excinfo.value)


def test_production_requires_malware_scanning() -> None:
    with pytest.raises(PydanticValidationError) as excinfo:
        Settings(**{**PRODUCTION_BASE, "malware_scanner": "none"})
    assert "VK_MALWARE_SCANNER" in str(excinfo.value)


def test_production_requires_master_key_for_local_provider() -> None:
    with pytest.raises(PydanticValidationError) as excinfo:
        Settings(**{**PRODUCTION_BASE, "master_key": None})
    assert "VK_MASTER_KEY" in str(excinfo.value)


def test_aws_kms_provider_needs_no_local_key() -> None:
    settings = Settings(**{**PRODUCTION_BASE, "master_key": None, "key_provider": "aws_kms"})
    assert settings.key_provider == "aws_kms"


def test_master_key_must_decode_to_32_bytes() -> None:
    settings = Settings(
        app_env="development", master_key=base64.urlsafe_b64encode(b"short").decode()
    )
    with pytest.raises(ValueError):
        _ = settings.master_key_bytes


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        Settings(app_env="development", log_level="LOUD")


def test_blank_optional_settings_are_treated_as_unset() -> None:
    """Docker/CI frequently export empty variables; those must mean "off"."""
    settings = Settings(
        app_env="development",
        sentry_dsn="",
        master_key="   ",
        s3_access_key="",
        cookie_domain="",
    )
    assert settings.sentry_dsn is None
    assert settings.master_key is None
    assert settings.s3_access_key is None
    assert settings.cookie_domain is None


def test_derived_collections_parse_comma_lists() -> None:
    settings = Settings(app_env="development")
    settings = settings.model_copy(
        update={
            "cors_origins": "https://a.example, https://b.example",
            "allowed_hosts": "api.example,localhost",
            "upload_allowed_mime_types": "application/pdf, IMAGE/PNG",
            "mfa_required_roles": "super_admin, institution_admin",
        }
    )
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]
    assert settings.allowed_host_list == ["api.example", "localhost"]
    assert settings.allowed_mime_types == frozenset({"application/pdf", "image/png"})
    assert settings.mfa_required_role_list == ["SUPER_ADMIN", "INSTITUTION_ADMIN"]

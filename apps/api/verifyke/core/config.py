"""Application configuration.

Every setting is externalised through environment variables (prefix ``VK_``) so
that no credential, key or endpoint is ever committed to source control. The
full list of supported variables is documented in ``.env.example`` at the
repository root.

Settings are validated on load: a production deployment refuses to start with a
default/weak secret, an insecure cookie policy or plain-HTTP public URLs.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "production"]
StorageBackend = Literal["s3", "local"]
MailBackend = Literal["smtp", "console"]
KeyProviderName = Literal["local", "aws_kms"]
MalwareScannerName = Literal["none", "clamav"]
PaymentProviderName = Literal["sandbox", "payhero"]

# The placeholder shipped in .env.example. It must never reach production; the
# production validator below rejects it explicitly.
DEV_SECRET_PLACEHOLDER = "dev-only-insecure-secret-change-me-0123456789abcdef"  # noqa: S105

# Roles that must enrol MFA before they can use the platform.
DEFAULT_MFA_REQUIRED_ROLES = "SUPER_ADMIN,INSTITUTION_ADMIN"


def _repo_root() -> Path:
    """Best-effort location of the repository root (used for default paths)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".env.example").exists() and (parent / "apps").exists():
            return parent
    return here.parents[4]


class Settings(BaseSettings):
    """Typed, validated application settings."""

    model_config = SettingsConfigDict(
        env_prefix="VK_",
        env_file=(".env", "../../.env", "../../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ app
    app_env: AppEnv = "development"
    app_name: str = "VerifyKE"
    app_version: str = "0.1.0"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Public URLs: `web` is the browser origin, `api` the origin used in
    # generated links (QR codes, verification URLs, emails).
    web_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    verify_path_prefix: str = "/verify"

    # ------------------------------------------------------------------ security
    secret_key: SecretStr = SecretStr(DEV_SECRET_PLACEHOLDER)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "verifyke"
    jwt_audience: str = "verifyke-web"
    access_token_ttl_minutes: int = 10
    refresh_token_ttl_days: int = 14
    # High-risk actions (key rotation, revocation, privilege change) require the
    # operator to have re-authenticated within this window.
    reauth_window_minutes: int = 5

    password_min_length: int = 12
    password_min_zxcvbn_score: int = 3

    # Cookie policy for the browser session (access + refresh + CSRF cookies).
    cookie_domain: str | None = None
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "strict"
    access_cookie_name: str = "vk_access"
    refresh_cookie_name: str = "vk_refresh"
    csrf_cookie_name: str = "vk_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    mfa_issuer_name: str = "VerifyKE"
    mfa_required_roles: str = DEFAULT_MFA_REQUIRED_ROLES

    # ------------------------------------------------------------------ database
    database_url: str = "postgresql+psycopg://verifyke:verifyke@localhost:5432/verifyke"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_recycle_seconds: int = 1800
    db_echo: bool = False
    db_statement_timeout_ms: int = 15_000

    # ------------------------------------------------------------------ cache / queue
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ------------------------------------------------------------------ object storage
    storage_backend: StorageBackend = "local"
    local_storage_path: Path = Field(default_factory=lambda: _repo_root() / ".runtime" / "storage")
    s3_endpoint_url: str | None = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_access_key: SecretStr | None = None
    s3_secret_key: SecretStr | None = None
    s3_bucket_certificates: str = "verifyke-certificates"
    s3_bucket_uploads: str = "verifyke-uploads"
    s3_bucket_institution_docs: str = "verifyke-institution-docs"
    signed_url_ttl_seconds: int = 300

    # ------------------------------------------------------------------ uploads
    upload_max_bytes: int = 10 * 1024 * 1024
    upload_allowed_mime_types: str = "application/pdf,image/png,image/jpeg"
    upload_pdf_max_pages: int = 20
    upload_image_max_pixels: int = 40_000_000
    malware_scanner: MalwareScannerName = "none"
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    clamav_timeout_seconds: int = 30

    # ------------------------------------------------------------------ OCR / document analysis
    ocr_enabled: bool = True
    ocr_min_confidence: float = 0.70
    tesseract_cmd: str = "tesseract"
    ocr_languages: str = "eng"
    document_analysis_enabled: bool = True

    # ------------------------------------------------------------------ mail
    mail_backend: MailBackend = "console"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_use_tls: bool = False
    mail_from: str = "no-reply@verifyke.local"
    mail_from_name: str = "VerifyKE"

    # ------------------------------------------------------------------ key management
    # `local` reads the master key from VK_MASTER_KEY (base64, 32 bytes).
    # `aws_kms` delegates wrapping/unwrapping to KMS and needs no local key.
    key_provider: KeyProviderName = "local"
    master_key: SecretStr | None = None
    aws_kms_region: str = "eu-west-1"
    aws_kms_key_id: str | None = None

    # ------------------------------------------------------------------ billing
    payment_provider: PaymentProviderName = "sandbox"
    payhero_base_url: str = "https://backend.payhero.co.ke/api/v2"
    payhero_auth_token: SecretStr | None = None
    payhero_channel_id: str | None = None
    payhero_webhook_secret: SecretStr | None = None
    billing_currency: str = "KES"

    # ------------------------------------------------------------------ rate limiting
    rate_limit_enabled: bool = True
    rate_limit_login: str = "10/5m"
    # A rate-limit rule ("5 per 15 minutes"), not a credential. Bandit flags the
    # field name; the noqa keeps the check enabled everywhere else.
    rate_limit_password_reset: str = "5/15m"  # noqa: S105
    rate_limit_register: str = "10/1h"
    rate_limit_verify_public: str = "60/1m"
    rate_limit_verify_upload: str = "20/5m"
    rate_limit_external_api: str = "600/1m"
    rate_limit_default: str = "300/1m"

    # ------------------------------------------------------------------ observability
    log_level: str = "INFO"
    log_json: bool | None = None  # None => JSON in production, console elsewhere
    metrics_enabled: bool = True
    sentry_dsn: SecretStr | None = None

    # ------------------------------------------------------------------ http
    cors_origins: str = "http://localhost:3000"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"

    # ------------------------------------------------------------------ privacy / retention
    privacy_retention_days_uploads: int = 30
    privacy_retention_days_audit_logs: int = 2557  # ~7 years
    public_verification_masks_names: bool = True

    # ------------------------------------------------------------------ validators
    @field_validator(
        "sentry_dsn",
        "master_key",
        "s3_access_key",
        "s3_secret_key",
        "smtp_username",
        "smtp_password",
        "payhero_auth_token",
        "payhero_channel_id",
        "payhero_webhook_secret",
        "aws_kms_key_id",
        "cookie_domain",
        mode="before",
    )
    @classmethod
    def _blank_optional_values_are_unset(cls, value: object) -> object:
        """Treat an empty environment variable as "not configured".

        A deployment (or Docker Compose) that exports ``VK_SENTRY_DSN=`` means "off",
        not "configured with an empty DSN" - without this, optional integrations
        would try to initialise themselves with blank credentials.
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        normalised = value.upper()
        if normalised not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return normalised

    @field_validator("api_v1_prefix")
    @classmethod
    def _validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("api_v1_prefix must start with '/'")
        return value.rstrip("/")

    @model_validator(mode="after")
    def _validate_environment(self) -> Settings:
        """Refuse to boot production with development-grade configuration."""
        if self.app_env != "production":
            return self
        problems: list[str] = []
        if self.secret_key.get_secret_value() == DEV_SECRET_PLACEHOLDER:
            problems.append("VK_SECRET_KEY must be replaced (default development value in use)")
        elif len(self.secret_key.get_secret_value()) < 32:
            problems.append("VK_SECRET_KEY must be at least 32 characters")
        if not self.cookie_secure:
            problems.append("VK_COOKIE_SECURE must be true in production")
        if self.debug:
            problems.append("VK_DEBUG must be false in production")
        for name, url in (
            ("VK_WEB_BASE_URL", self.web_base_url),
            ("VK_API_BASE_URL", self.api_base_url),
        ):
            if not url.startswith("https://"):
                problems.append(f"{name} must use https in production")
        if self.key_provider == "local" and not self.master_key:
            problems.append("VK_MASTER_KEY is required when VK_KEY_PROVIDER=local")
        if self.malware_scanner == "none":
            problems.append("VK_MALWARE_SCANNER must be clamav in production")
        if problems:
            raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self

    # ------------------------------------------------------------------ derived values
    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def json_logs(self) -> bool:
        return self.is_production if self.log_json is None else self.log_json

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def allowed_mime_types(self) -> frozenset[str]:
        return frozenset(
            m.strip().lower() for m in self.upload_allowed_mime_types.split(",") if m.strip()
        )

    @property
    def mfa_required_role_list(self) -> list[str]:
        return [role.strip().upper() for role in self.mfa_required_roles.split(",") if role.strip()]

    @property
    def master_key_bytes(self) -> bytes | None:
        """Decoded 32-byte master key material, or ``None`` when unset."""
        if self.master_key is None:
            return None
        raw = self.master_key.get_secret_value()
        try:
            decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        except (ValueError, TypeError) as exc:
            raise ValueError("VK_MASTER_KEY must be base64-encoded") from exc
        if len(decoded) != 32:
            raise ValueError("VK_MASTER_KEY must decode to exactly 32 bytes (AES-256)")
        return decoded


def apply_test_overrides(settings_instance: Settings, overrides: dict[str, object]) -> Settings:
    """Return a copy of ``settings_instance`` with explicit overrides applied.

    Used by the test-suite (settable field names only) - production code always
    reads configuration from the environment.
    """
    unknown = set(overrides) - set(Settings.model_fields)
    if unknown:
        raise ValueError(f"Unknown settings override(s): {sorted(unknown)}")
    return settings_instance.model_copy(update=overrides)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()


settings = get_settings()

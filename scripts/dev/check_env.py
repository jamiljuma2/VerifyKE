#!/usr/bin/env python3
"""Preflight check: can this machine run VerifyKE right now?

    python scripts/dev/check_env.py

Verifies, without modifying anything:
  1. .env exists and the required secrets are set (and not placeholders)
  2. PostgreSQL is reachable and the expected extensions are installed
  3. Redis answers PING
  4. Object storage is reachable (only when VK_STORAGE_BACKEND=s3)
  5. Tesseract is available (only when OCR is enabled)

Exit code 0 means the API can start and serve requests.
"""

from __future__ import annotations

import base64
import os
import shutil
import socket
import sys
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"

OK = "  [ok]  "
WARN = " [warn] "
FAIL = " [FAIL] "


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"')
    return values


def report(status: str, message: str) -> bool:
    print(f"{status}{message}")
    return status == OK


def check_env_file(env: dict[str, str]) -> bool:
    if not env:
        return report(FAIL, ".env not found - run: cp .env.example .env && make secrets")

    healthy = report(OK, ".env found")
    required = ("VK_SECRET_KEY", "VK_DATABASE_URL", "VK_REDIS_URL")
    for key in required:
        if not env.get(key):
            healthy = report(FAIL, f"{key} is empty") and healthy

    secret = env.get("VK_SECRET_KEY", "")
    if secret and ("change-me" in secret or "insecure" in secret):
        healthy = report(WARN, "VK_SECRET_KEY still looks like a placeholder") and healthy
    elif secret and len(secret) < 32:
        healthy = report(WARN, "VK_SECRET_KEY is shorter than 32 characters") and healthy

    if env.get("VK_KEY_PROVIDER", "local") == "local":
        master = env.get("VK_MASTER_KEY", "")
        if not master:
            healthy = report(WARN, "VK_MASTER_KEY is not set - signing keys cannot be protected") and healthy
        else:
            try:
                decoded = base64.urlsafe_b64decode(master + "=" * (-len(master) % 4))
                if len(decoded) != 32:
                    healthy = report(FAIL, "VK_MASTER_KEY must decode to 32 bytes") and healthy
            except Exception:
                healthy = report(FAIL, "VK_MASTER_KEY is not valid base64") and healthy
    return healthy


def check_database(url: str) -> bool:
    if not url:
        return report(FAIL, "VK_DATABASE_URL is not set")

    try:
        import psycopg
    except ImportError:
        return report(WARN, "psycopg is not installed in this interpreter - skipping")

    sync_url = url.replace("+psycopg", "").replace("+asyncpg", "")
    try:
        with psycopg.connect(sync_url, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0].split(",")[0]
                cursor.execute("SELECT extname FROM pg_extension")
                extensions = {row[0] for row in cursor.fetchall()}
    except Exception as exc:
        return report(FAIL, f"PostgreSQL unreachable: {type(exc).__name__}: {exc}")

    healthy = report(OK, f"PostgreSQL reachable ({version})")
    for extension in ("pgcrypto", "citext", "pg_trgm"):
        if extension not in extensions:
            healthy = report(WARN, f"extension {extension} is missing (run infrastructure/postgres/init/01-extensions.sql)") and healthy
    return healthy


def check_redis(url: str) -> bool:
    if not url:
        return report(FAIL, "VK_REDIS_URL is not set")
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=3) as connection:
            connection.sendall(b"*1\r\n$4\r\nPING\r\n")
            if not connection.recv(64).startswith(b"+PONG"):
                return report(FAIL, f"Redis at {host}:{port} did not answer PING")
    except OSError as exc:
        return report(FAIL, f"Redis unreachable at {host}:{port} ({exc})")
    return report(OK, f"Redis reachable at {host}:{port}")


def check_storage(env: dict[str, str]) -> bool:
    if env.get("VK_STORAGE_BACKEND", "s3") != "s3":
        return report(OK, "storage backend is 'local' - skipping S3 check")
    endpoint = env.get("VK_S3_ENDPOINT_URL", "")
    if not endpoint:
        return report(WARN, "VK_S3_ENDPOINT_URL is not set")
    parsed = urllib.parse.urlparse(endpoint)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=3):
            pass
    except OSError as exc:
        return report(FAIL, f"object storage unreachable at {host}:{port} ({exc})")
    return report(OK, f"object storage reachable at {host}:{port}")


def check_ocr(env: dict[str, str]) -> bool:
    if env.get("VK_OCR_ENABLED", "true").lower() != "true":
        return report(OK, "OCR disabled - skipping Tesseract check")
    binary = env.get("VK_TESSERACT_CMD", "tesseract")
    if shutil.which(binary) is None:
        return report(WARN, f"'{binary}' not found - image and PDF text extraction will be limited")
    return report(OK, f"Tesseract available ({binary})")


def main() -> int:
    print("VerifyKE preflight\n=================")
    env = load_env()
    results = [
        check_env_file(env),
        check_database(env.get("VK_DATABASE_URL", "")),
        check_redis(env.get("VK_REDIS_URL", "")),
        check_storage(env),
        check_ocr(env),
    ]

    print("\nResult:", "ready" if all(results) else "not ready - see the [FAIL]/[warn] lines above")
    # Warnings do not fail the check; errors do.
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())

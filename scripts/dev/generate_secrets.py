#!/usr/bin/env python3
"""Generate strong development secrets and update .env in place.

Usage (from the repository root):

    python scripts/dev/generate_secrets.py            # update .env
    python scripts/dev/generate_secrets.py --dry-run  # print only

What it writes:
  VK_SECRET_KEY          application/JWT signing secret (48 bytes, url-safe)
  VK_MASTER_KEY          AES-256 key material for the local key provider (32 bytes,
                         base64) - the root of the institution key hierarchy
  POSTGRES_PASSWORD      database password
  MINIO_ROOT_PASSWORD    object storage password

Existing non-empty values are never overwritten unless --force is passed, so
running this twice cannot silently invalidate issued certificates (rotating
VK_MASTER_KEY makes previously wrapped institution keys unreadable).
"""

from __future__ import annotations

import argparse
import base64
import re
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

PLACEHOLDER_MARKERS = ("change", "replace", "insecure", "dev-only", "example")


def generate_values() -> dict[str, str]:
    return {
        "VK_SECRET_KEY": secrets.token_urlsafe(48),
        "VK_MASTER_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
        "MINIO_ROOT_PASSWORD": secrets.token_urlsafe(24),
        "VK_PAYHERO_WEBHOOK_SECRET": secrets.token_urlsafe(32),
    }


def is_placeholder(value: str) -> bool:
    lowered = value.strip().strip('"').lower()
    if lowered == "":
        return True
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def rewrite(content: str, values: dict[str, str], force: bool) -> tuple[str, list[str], list[str]]:
    updated: list[str] = []
    preserved: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        current = match.group(2)
        if key not in values:
            return match.group(0)
        if not force and not is_placeholder(current):
            preserved.append(key)
            return match.group(0)
        updated.append(key)
        return f"{key}={values[key]}"

    pattern = re.compile(rf"^({'|'.join(map(re.escape, values))})=(.*)$", re.MULTILINE)
    return pattern.sub(replace, content), updated, preserved


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate VerifyKE development secrets")
    parser.add_argument("--dry-run", action="store_true", help="print values without writing")
    parser.add_argument("--force", action="store_true", help="overwrite existing values")
    args = parser.parse_args()

    values = generate_values()

    if args.dry_run:
        for key, value in values.items():
            print(f"{key}={value}")
        return 0

    if not ENV_PATH.exists():
        if not ENV_EXAMPLE_PATH.exists():
            print("error: .env.example is missing; cannot create .env", file=sys.stderr)
            return 1
        ENV_PATH.write_text(ENV_EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print("Created .env from .env.example")

    content = ENV_PATH.read_text(encoding="utf-8")
    new_content, updated, preserved = rewrite(content, values, args.force)
    ENV_PATH.write_text(new_content, encoding="utf-8")

    for key in updated:
        print(f"generated {key}")
    for key in preserved:
        print(f"kept existing {key} (use --force to rotate)")

    missing = set(values) - set(updated) - set(preserved)
    for key in sorted(missing):
        print(f"warning: {key} is not present in .env - add it manually", file=sys.stderr)

    if "VK_MASTER_KEY" in updated or (args.force and "VK_MASTER_KEY" in values):
        print(
            "\nNOTE: rotating VK_MASTER_KEY makes keys wrapped with the previous master key\n"
            "unreadable. Rotate it only before issuing certificates or through the\n"
            "documented key-rotation procedure (see docs/security.md)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

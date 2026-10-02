"""Alembic environment.

The database URL comes from the environment (``VK_DATABASE_URL``) via the
application settings - never from alembic.ini - so no credential is committed.

Migrations run with a synchronous psycopg connection. Autogenerate compares both
types and server defaults, and every migration is expected to be reviewed by a
human before it is applied (see docs/database.md).
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make ``verifyke`` importable when alembic is invoked from apps/api.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verifyke.core.config import get_settings
from verifyke.core.db import Base
from verifyke.models import load_all_models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# Register every ORM model on Base.metadata so autogenerate detects changes.
load_all_models()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade --sql``)."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            # Advisory lock so two deployments cannot migrate concurrently.
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

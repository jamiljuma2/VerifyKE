"""Tenant core: institution, role, user and institution_key.

Creates the four tables that define the tenant boundary, plus the row-level
security policies from ``docs/database.md`` section 3 that make the boundary
enforced by the database rather than only by application code.

Reviewed against the checklist in ``docs/database.md`` section 4:

1. Locking: this only creates tables, so there is nothing to lock yet.
2. Reversible: yes - ``downgrade()`` drops in reverse dependency order and
   drops the enum types explicitly, which autogenerate does not do.
3. Grants/RLS: yes - policies are created below and grants are applied to
   ``verifyke_app`` when that role exists.
4. Indexes: no ``CONCURRENTLY`` needed, the tables are empty.

A note on ``FORCE ROW LEVEL SECURITY``: it is applied so the policies bind even
when the connecting role owns the table. The role must still lack ``BYPASSRLS``
- see the warning in ``infrastructure/postgres/init/01-extensions.sql``.

Revision ID: 0bfdfc963f74
Revises:
Create Date: 2026-10-03 02:10:41.907101
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0bfdfc963f74"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables carrying tenant data, which therefore get row-level security.
# ``institution`` and ``role`` are deliberately excluded: an institution row is
# the tenant *definition*, not tenant data, and roles are global reference data.
RLS_TABLES = ("user", "institution_key")

ROLE_CODES = ("SUPER_ADMIN", "INSTITUTION_ADMIN", "INSTITUTION_ISSUER", "VERIFIER", "AUDITOR")

ROLE_SEED = (
    ("SUPER_ADMIN", "Platform administrator", True),
    ("INSTITUTION_ADMIN", "Institution administrator", False),
    ("INSTITUTION_ISSUER", "Certificate issuer", False),
    ("VERIFIER", "Verifier", False),
    ("AUDITOR", "Compliance auditor", False),
)


def _timestamps() -> tuple[sa.Column, sa.Column]:
    """The ``created_at``/``updated_at`` pair shared by every table."""
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.create_table(
        "institution",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACTIVE", "SUSPENDED", "REJECTED", name="institution_status"),
            nullable=False,
        ),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("regulator_name", sa.String(length=255), nullable=True),
        sa.Column("regulator_code", sa.String(length=16), nullable=True),
        sa.Column("contact_email", postgresql.CITEXT(), nullable=False),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("address_line", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("certificate_prefix", sa.String(length=16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institution")),
        sa.CheckConstraint(
            "char_length(country_code) = 2",
            name=op.f("ck_institution_country_code_length"),
        ),
    )
    op.create_index(op.f("ix_institution_created_at"), "institution", ["created_at"])
    op.create_index(op.f("ix_institution_deleted_at"), "institution", ["deleted_at"])
    op.create_index(op.f("ix_institution_slug"), "institution", ["slug"], unique=True)
    op.create_index(op.f("ix_institution_status"), "institution", ["status"])

    op.create_table(
        "role",
        sa.Column("code", sa.Enum(*ROLE_CODES, name="role_code"), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_platform", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role")),
        sa.UniqueConstraint("code", name="uq_role_code"),
    )
    op.create_index(op.f("ix_role_code"), "role", ["code"])
    op.create_index(op.f("ix_role_created_at"), "role", ["created_at"])

    op.create_table(
        "institution_key",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "RETIRED", "COMPROMISED", name="institution_key_status"),
            nullable=False,
        ),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("wrapped_private_key", sa.LargeBinary(), nullable=False),
        sa.Column("key_provider", sa.String(length=32), nullable=False),
        sa.Column("provider_key_ref", sa.String(length=255), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("compromised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institution.id"],
            name=op.f("fk_institution_key_institution_id_institution"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institution_key")),
        sa.UniqueConstraint("institution_id", "version", name="uq_institution_key_version"),
        sa.CheckConstraint("version >= 1", name="ck_institution_key_version_positive"),
    )
    op.create_index(op.f("ix_institution_key_created_at"), "institution_key", ["created_at"])
    op.create_index(
        op.f("ix_institution_key_institution_id"), "institution_key", ["institution_id"]
    )
    op.create_index(op.f("ix_institution_key_status"), "institution_key", ["status"])

    op.create_table(
        "user",
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column(
            "role_code",
            sa.Enum(*ROLE_CODES, name="role_code", create_type=False),
            nullable=False,
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "ACTIVE", "LOCKED", "DISABLED", name="user_status"),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "mfa_method",
            sa.Enum("TOTP", "RECOVERY_CODE", name="mfa_method"),
            nullable=True,
        ),
        sa.Column("mfa_secret_encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("mfa_enrolled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("must_change_password", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_ip", sa.String(length=45), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institution.id"],
            name=op.f("fk_user_institution_id_institution"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
        sa.UniqueConstraint("institution_id", "email", name="uq_user_institution_email"),
        # A platform administrator has no institution, so the constraint above
        # cannot protect their address: NULLs do not collide in UNIQUE. Enforce
        # the tenant/platform relationship in both directions instead.
        sa.CheckConstraint(
            "(institution_id IS NULL) = (role_code = 'SUPER_ADMIN')",
            name=op.f("ck_user_platform_requires_super_admin"),
        ),
    )
    op.create_index(op.f("ix_user_created_at"), "user", ["created_at"])
    op.create_index(op.f("ix_user_deleted_at"), "user", ["deleted_at"])
    op.create_index(op.f("ix_user_institution_id"), "user", ["institution_id"])
    op.create_index(op.f("ix_user_role_code"), "user", ["role_code"])
    op.create_index(op.f("ix_user_status"), "user", ["status"])
    # Unique on email alone for live rows: two soft-deleted users may share an
    # address, but only one live row may hold it.
    op.create_index(
        "ix_user_email_active",
        "user",
        ["email"],
        unique=True,
        postgresql_where="deleted_at IS NULL",
    )

    _seed_roles()
    _create_updated_at_triggers()
    _enable_row_level_security()
    _grant_runtime_access()


def _seed_roles() -> None:
    """Insert the fixed role set.

    Written as plain SQL rather than ``bulk_insert`` so the id is generated by
    the database (``gen_random_uuid()`` is a function, not a bindable value,
    which ``executemany`` cannot adapt).
    """
    values = ", ".join(
        f"('{code}', '{label}', '{label}', {'true' if is_platform else 'false'})"
        for code, label, is_platform in ROLE_SEED
    )
    op.execute(
        f"""
        INSERT INTO role (code, label, description, is_platform, id)
        SELECT seed.code::role_code, seed.label, seed.description, seed.is_platform,
               gen_random_uuid()
        FROM (VALUES {values})
             AS seed(code, label, description, is_platform)
        """
    )


def _qt(table: str) -> str:
    """Quote a table identifier for raw SQL.

    ``user`` is a reserved word in PostgreSQL, so unquoted it is a syntax
    error. SQLAlchemy quotes identifiers for the DDL it emits, but the RLS and
    trigger statements below are hand-written and must do it themselves.
    """
    return f'"{table}"'


def _create_updated_at_triggers() -> None:
    """Refresh ``updated_at`` on UPDATE.

    A trigger rather than an ORM event, so a bulk SQL update (a data migration,
    a retention job) cannot silently leave a stale timestamp behind.
    """
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
          NEW.updated_at = now();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in ("institution", "role", "institution_key", "user"):
        quoted = _qt(table)
        op.execute(
            f"""
            CREATE TRIGGER {_qt(f"{table}_set_updated_at")}
              BEFORE UPDATE ON {quoted}
              FOR EACH ROW
              EXECUTE FUNCTION set_updated_at()
            """
        )


def _enable_row_level_security() -> None:
    """Isolate tenants in the database, not just in the application.

    ``tenant_isolation`` keys on the transaction-local
    ``app.current_institution`` setting, so a query that forgot its
    ``WHERE institution_id = ...`` still cannot read another tenant's rows.

    ``platform_read`` covers platform-level operations (public verification,
    cross-tenant reporting): they run with an empty setting and may read, but
    the policy grants SELECT only - it does not disable RLS.
    """
    for table in RLS_TABLES:
        quoted = _qt(table)
        op.execute(f"ALTER TABLE {quoted} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {_qt(f"{table}_tenant_isolation")} ON {quoted}
              USING (
                institution_id = NULLIF(
                  current_setting('app.current_institution', true), ''
                )::uuid
              )
              WITH CHECK (
                institution_id = NULLIF(
                  current_setting('app.current_institution', true), ''
                )::uuid
              )
            """
        )
        op.execute(
            f"""
            CREATE POLICY {_qt(f"{table}_platform_read")} ON {quoted}
              FOR SELECT
              USING (
                NULLIF(current_setting('app.current_institution', true), '') IS NULL
              )
            """
        )


def _grant_runtime_access() -> None:
    """Least privilege for the runtime role, when the bootstrap created it."""
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'verifyke_app') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE
              ON institution, role, "user", institution_key TO verifyke_app;
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO verifyke_app;
          END IF;
        END
        $$
        """
    )
    # Nothing is readable by an unprivileged session by accident.
    op.execute('REVOKE ALL ON institution, role, "user", institution_key FROM PUBLIC')


def downgrade() -> None:
    for table in reversed(RLS_TABLES):
        quoted = _qt(table)
        op.execute(f"DROP POLICY IF EXISTS {_qt(f'{table}_platform_read')} ON {quoted}")
        op.execute(f"DROP POLICY IF EXISTS {_qt(f'{table}_tenant_isolation')} ON {quoted}")
        op.execute(f"ALTER TABLE {quoted} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted} DISABLE ROW LEVEL SECURITY")

    for table in ("user", "institution_key", "role", "institution"):
        op.execute(f"DROP TRIGGER IF EXISTS {_qt(f'{table}_set_updated_at')} ON {_qt(table)}")

    op.drop_index("ix_user_email_active", table_name="user")
    op.drop_index(op.f("ix_user_status"), table_name="user")
    op.drop_index(op.f("ix_user_role_code"), table_name="user")
    op.drop_index(op.f("ix_user_institution_id"), table_name="user")
    op.drop_index(op.f("ix_user_created_at"), table_name="user")
    op.drop_index(op.f("ix_user_deleted_at"), table_name="user")
    op.drop_table("user")

    op.drop_index(op.f("ix_institution_key_status"), table_name="institution_key")
    op.drop_index(op.f("ix_institution_key_institution_id"), table_name="institution_key")
    op.drop_index(op.f("ix_institution_key_created_at"), table_name="institution_key")
    op.drop_table("institution_key")

    op.drop_index(op.f("ix_role_created_at"), table_name="role")
    op.drop_index(op.f("ix_role_code"), table_name="role")
    op.drop_table("role")

    op.drop_index(op.f("ix_institution_status"), table_name="institution")
    op.drop_index(op.f("ix_institution_slug"), table_name="institution")
    op.drop_index(op.f("ix_institution_deleted_at"), table_name="institution")
    op.drop_index(op.f("ix_institution_created_at"), table_name="institution")
    op.drop_table("institution")

    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")

    # Enum types outlive their tables, so they are dropped explicitly.
    bind = op.get_bind()
    postgresql.ENUM(name="mfa_method").drop(bind, checkfirst=True)
    postgresql.ENUM(name="user_status").drop(bind, checkfirst=True)
    postgresql.ENUM(*ROLE_CODES, name="role_code").drop(bind, checkfirst=True)
    postgresql.ENUM(name="institution_key_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="institution_status").drop(bind, checkfirst=True)

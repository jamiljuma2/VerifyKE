-- VerifyKE database bootstrap (runs once, on first cluster start).
--
-- Extensions:
--   pgcrypto    digest()/gen_random_bytes() for migration-time hashing
--   citext      case-insensitive unique emails and certificate ids
--   pg_trgm     fast fuzzy search over institution/certificate references
--   unaccent    accent-insensitive holder-name search
--
-- Row-level security itself is created by Alembic migrations so that policies
-- live in version control next to the tables they protect.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Dedicated runtime role for the application.
--
-- NOTE: the application connects as the owner in development for convenience,
-- but production deployments should set VK_DATABASE_URL to a role WITHOUT
-- BYPASSRLS, otherwise row-level security is silently ineffective.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'verifyke_app') THEN
    CREATE ROLE verifyke_app LOGIN PASSWORD 'change-me-in-production' NOSUPERUSER NOBYPASSRLS;
  END IF;
END
$$;

-- Least privilege: the runtime role may use the schema but not create objects.
GRANT USAGE ON SCHEMA public TO verifyke_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO verifyke_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO verifyke_app;

-- Statement timeouts protect the database from a runaway query in the API.
DO $$
BEGIN
  EXECUTE format('ALTER DATABASE %I SET statement_timeout = %L', current_database(), '15s');
  EXECUTE format('ALTER DATABASE %I SET idle_in_transaction_session_timeout = %L', current_database(), '30s');
  EXECUTE format('ALTER DATABASE %I SET lock_timeout = %L', current_database(), '5s');
END
$$;

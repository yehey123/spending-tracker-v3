"""Create non-superuser app_user role for runtime DB connections.

Postgres superusers bypass RLS unconditionally — FORCE ROW LEVEL SECURITY does
not override superuser status. The app must connect as a non-superuser role so
that the RLS policies created in 0010 are actually enforced.

This migration creates 'app_user' (non-superuser, no BYPASSRLS), grants it the
minimum privileges needed for the application, and sets DEFAULT PRIVILEGES so
that tables added in future migrations inherit the same grants automatically.
"""

import os
import re
from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pwd = os.environ.get('APP_DB_PASSWORD', 'app_password')
    if not re.match(r'^[A-Za-z0-9_@#$!%^&*()\-+=.]+$', pwd):
        raise ValueError("APP_DB_PASSWORD contains characters that are not allowed")

    # Create or update the app_user role (idempotent).
    op.execute(f"""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
            CREATE ROLE app_user WITH LOGIN PASSWORD '{pwd}' NOSUPERUSER NOBYPASSRLS;
          ELSE
            ALTER ROLE app_user WITH PASSWORD '{pwd}' NOSUPERUSER NOBYPASSRLS LOGIN;
          END IF;
        END
        $$
    """)

    # CONNECT on the current database (works for both spending_tracker and the test DB).
    op.execute("""
        DO $$
        BEGIN
          EXECUTE 'GRANT CONNECT ON DATABASE ' || quote_ident(current_database()) || ' TO app_user';
        END
        $$
    """)

    op.execute("GRANT USAGE ON SCHEMA public TO app_user")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user"
    )
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user")

    # Future tables / sequences created by the superuser inherit these grants.
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user
    """)
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT USAGE, SELECT ON SEQUENCES TO app_user
    """)


def downgrade() -> None:
    # Revoke per-database privileges but do NOT drop the role.
    # app_user is a cluster-level object and may hold privileges in other databases
    # (e.g. both spending_tracker and spending_tracker_test); DROP ROLE would require
    # revoking all grants across every database, which this single-database downgrade
    # cannot do safely.
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE
        ON TABLES FROM app_user
    """)
    op.execute("""
        ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM app_user
    """)
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_user")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_user")
    op.execute("REVOKE USAGE ON SCHEMA public FROM app_user")
    op.execute("""
        DO $$
        BEGIN
          EXECUTE 'REVOKE CONNECT ON DATABASE '
            || quote_ident(current_database()) || ' FROM app_user';
        END
        $$
    """)

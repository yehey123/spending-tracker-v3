"""Multi-tenant isolation: user_id FK + RLS on core tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 1: reset existing data — no production users exist yet.
    # user_id cannot be backfilled from real identities; clearing ensures a
    # clean RLS-enforced start.
    op.execute("DELETE FROM transactions")
    op.execute("DELETE FROM statements")
    op.execute("DELETE FROM categories WHERE is_system = FALSE")
    op.execute("DELETE FROM app_settings")

    # Phase 2 — ADD COLUMN user_id on four tables
    op.add_column('statements',
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=True))

    op.add_column('transactions',
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=True))

    op.add_column('categories',
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=True))

    op.add_column('app_settings',
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=True))

    op.create_index('ix_statements_user_id', 'statements', ['user_id'])
    op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('ix_app_settings_user_id', 'app_settings', ['user_id'])
    op.create_index('ix_categories_user_id', 'categories', ['user_id'])

    op.create_unique_constraint('uq_app_settings_user_id', 'app_settings', ['user_id'])

    # Give app_settings an auto-increment default so new per-user rows get unique ids.
    op.execute("CREATE SEQUENCE IF NOT EXISTS app_settings_id_seq START 2")
    op.execute("ALTER TABLE app_settings ALTER COLUMN id SET DEFAULT nextval('app_settings_id_seq')")

    # Phase 3 — ENABLE ROW LEVEL SECURITY
    for table in ('statements', 'transactions', 'categories', 'app_settings'):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    # Phase 4 — RLS policies for regular users
    # Null-safe: NULLIF handles the case where app.user_id is not set,
    # returning NULL instead of raising an error on empty-string-to-uuid cast.
    op.execute("""
        CREATE POLICY statements_user_isolation ON statements
        FOR ALL
        USING (user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid)
        WITH CHECK (user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid)
    """)

    op.execute("""
        CREATE POLICY transactions_user_isolation ON transactions
        FOR ALL
        USING (user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid)
        WITH CHECK (user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid)
    """)

    # Categories: user sees their own AND system categories (user_id = NULL, is_system = TRUE).
    # WITH CHECK restricts creation to rows owned by the requesting user.
    op.execute("""
        CREATE POLICY categories_user_isolation ON categories
        FOR ALL
        USING (
            is_system = TRUE
            OR user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid
        )
        WITH CHECK (
            user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid
        )
    """)

    op.execute("""
        CREATE POLICY app_settings_user_isolation ON app_settings
        FOR ALL
        USING (user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid)
        WITH CHECK (user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid)
    """)

    # Phase 5 — Admin bypass policies
    op.execute("""
        CREATE POLICY statements_admin_bypass ON statements
        FOR ALL
        USING (current_setting('app.is_admin', TRUE) = 'true')
        WITH CHECK (current_setting('app.is_admin', TRUE) = 'true')
    """)

    op.execute("""
        CREATE POLICY transactions_admin_bypass ON transactions
        FOR ALL
        USING (current_setting('app.is_admin', TRUE) = 'true')
        WITH CHECK (current_setting('app.is_admin', TRUE) = 'true')
    """)

    op.execute("""
        CREATE POLICY categories_admin_bypass ON categories
        FOR ALL
        USING (current_setting('app.is_admin', TRUE) = 'true')
        WITH CHECK (current_setting('app.is_admin', TRUE) = 'true')
    """)

    op.execute("""
        CREATE POLICY app_settings_admin_bypass ON app_settings
        FOR ALL
        USING (current_setting('app.is_admin', TRUE) = 'true')
        WITH CHECK (current_setting('app.is_admin', TRUE) = 'true')
    """)


def downgrade() -> None:
    for table in ('statements', 'transactions', 'categories', 'app_settings'):
        op.execute(f"DROP POLICY IF EXISTS {table}_admin_bypass ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_user_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("ALTER TABLE app_settings ALTER COLUMN id DROP DEFAULT")
    op.execute("DROP SEQUENCE IF EXISTS app_settings_id_seq")

    op.drop_constraint('uq_app_settings_user_id', 'app_settings', type_='unique')
    op.drop_index('ix_categories_user_id', table_name='categories')
    op.drop_index('ix_app_settings_user_id', table_name='app_settings')
    op.drop_index('ix_transactions_user_id', table_name='transactions')
    op.drop_index('ix_statements_user_id', table_name='statements')

    op.drop_column('app_settings', 'user_id')
    op.drop_column('categories', 'user_id')
    op.drop_column('transactions', 'user_id')
    op.drop_column('statements', 'user_id')

"""Add credit_ledger, credit_rollovers, and db_config tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'db_config',
        sa.Column('key', sa.Text(), primary_key=True, nullable=False),
        sa.Column('value', JSONB(), nullable=False),
    )
    # provider names match _resolve_ocr branches: anthropic, openai, gemini, vertex
    op.execute("""
        INSERT INTO db_config (key, value) VALUES
          ('credit_weights',    '{"tesseract": 0, "anthropic": 3, "openai": 3, "gemini": 2, "vertex": 2}'),
          ('monthly_grant',     '30')
        ON CONFLICT (key) DO NOTHING
    """)

    op.create_table(
        'credit_ledger',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('ref_id', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.Text(), nullable=True, unique=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_credit_ledger_user_id', 'credit_ledger', ['user_id'])
    op.create_index('ix_credit_ledger_created_at', 'credit_ledger', ['created_at'])

    op.create_table(
        'credit_rollovers',
        sa.Column('user_id', UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('period', sa.Date(), nullable=False),
        sa.Column('credits_given', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'period'),
    )

    # RLS — same pattern as 0010 (statements, transactions, categories, app_settings)
    for table in ('credit_ledger', 'credit_rollovers'):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY credit_ledger_user_isolation ON credit_ledger
        FOR ALL
        USING (user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid)
        WITH CHECK (user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid)
    """)
    op.execute("""
        CREATE POLICY credit_ledger_admin_bypass ON credit_ledger
        FOR ALL
        USING (current_setting('app.is_admin', TRUE) = 'true')
        WITH CHECK (current_setting('app.is_admin', TRUE) = 'true')
    """)

    op.execute("""
        CREATE POLICY credit_rollovers_user_isolation ON credit_rollovers
        FOR ALL
        USING (user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid)
        WITH CHECK (user_id = NULLIF(current_setting('app.user_id', TRUE), '')::uuid)
    """)
    op.execute("""
        CREATE POLICY credit_rollovers_admin_bypass ON credit_rollovers
        FOR ALL
        USING (current_setting('app.is_admin', TRUE) = 'true')
        WITH CHECK (current_setting('app.is_admin', TRUE) = 'true')
    """)


def downgrade() -> None:
    for table in ('credit_ledger', 'credit_rollovers'):
        op.execute(f"DROP POLICY IF EXISTS {table}_admin_bypass ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_user_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_table('credit_rollovers')
    op.drop_index('ix_credit_ledger_created_at', table_name='credit_ledger')
    op.drop_index('ix_credit_ledger_user_id', table_name='credit_ledger')
    op.drop_table('credit_ledger')
    op.drop_table('db_config')

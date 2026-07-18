"""New tables: transaction_flags, merchant_category_memory, audit_log; pg_trgm GIN index"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('transaction_flags',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('transaction_id', sa.Integer(),
                  sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('flag_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.String(20), nullable=True),
    )
    op.create_index('idx_tf_tx_status', 'transaction_flags', ['transaction_id', 'status'])
    op.create_index('idx_tf_type_status', 'transaction_flags', ['flag_type', 'status'])

    op.create_table('merchant_category_memory',
        sa.Column('description_normalized', sa.String(200), primary_key=True),
        sa.Column('category_id', sa.Integer(),
                  sa.ForeignKey('categories.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source', sa.String(30), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_used_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
    )

    op.create_table('audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('transaction_id', sa.Integer(),
                  sa.ForeignKey('transactions.id'), nullable=False),
        sa.Column('field', sa.String(50), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('changed_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('changed_by', sa.String(20), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
    )

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
        CREATE INDEX idx_transactions_description_trgm
          ON transactions USING GIN (description gin_trgm_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_transactions_description_trgm")
    op.drop_table('audit_log')
    op.drop_table('merchant_category_memory')
    op.drop_index('idx_tf_type_status', table_name='transaction_flags')
    op.drop_index('idx_tf_tx_status', table_name='transaction_flags')
    op.drop_table('transaction_flags')

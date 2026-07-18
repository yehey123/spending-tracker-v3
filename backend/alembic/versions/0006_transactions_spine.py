"""transactions spine: status, origin, timestamps, parent FK, reversal FKs

NOTE: currency column was added in 0004 — skipped here to avoid duplicate column error.
"""

from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('status', sa.String(20),
                  nullable=False, server_default='active'))
    op.add_column('transactions', sa.Column('transaction_origin', sa.String(20),
                  nullable=False, server_default='uploaded'))
    op.add_column('transactions', sa.Column('created_at',
                  sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')))
    op.add_column('transactions', sa.Column('updated_at',
                  sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text('NOW()')))

    op.add_column('transactions', sa.Column('parent_transaction_id',
                  sa.Integer(), sa.ForeignKey('transactions.id', ondelete='SET NULL'),
                  nullable=True))
    op.add_column('transactions', sa.Column('reversal_of',
                  sa.Integer(), sa.ForeignKey('transactions.id'), nullable=True))
    op.add_column('transactions', sa.Column('reversal_reason', sa.String(200), nullable=True))
    op.add_column('transactions', sa.Column('reversed_by',
                  sa.Integer(), sa.ForeignKey('transactions.id'), nullable=True))
    op.add_column('transactions', sa.Column('correction_of',
                  sa.Integer(), sa.ForeignKey('transactions.id'), nullable=True))
    op.add_column('transactions', sa.Column('corrected_by',
                  sa.Integer(), sa.ForeignKey('transactions.id'), nullable=True))

    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_transactions_updated_at
          BEFORE UPDATE ON transactions
          FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_transactions_updated_at ON transactions")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    for col in ('corrected_by', 'correction_of', 'reversed_by',
                'reversal_reason', 'reversal_of', 'parent_transaction_id',
                'updated_at', 'created_at', 'transaction_origin', 'status'):
        op.drop_column('transactions', col)

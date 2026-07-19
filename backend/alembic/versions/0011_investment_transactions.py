"""Investment transactions table for broker accounts"""

from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('investment_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(),
                  sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('statement_id', sa.Integer(),
                  sa.ForeignKey('statements.id', ondelete='SET NULL'), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('shares', sa.Numeric(18, 6), nullable=False),
        sa.Column('price_per_share', sa.Numeric(18, 6), nullable=False),
        sa.Column('amount', sa.Numeric(18, 2), nullable=False),
        sa.Column('direction', sa.String(10), nullable=False),
        sa.Column('commission', sa.Numeric(12, 2), nullable=True),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
    )
    op.create_index('idx_inv_tx_account', 'investment_transactions', ['account_id'])
    op.create_index('idx_inv_tx_symbol', 'investment_transactions', ['symbol'])


def downgrade() -> None:
    op.drop_index('idx_inv_tx_symbol', table_name='investment_transactions')
    op.drop_index('idx_inv_tx_account', table_name='investment_transactions')
    op.drop_table('investment_transactions')

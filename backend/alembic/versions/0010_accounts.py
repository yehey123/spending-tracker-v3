"""Accounts table + account_id FK on transactions and statements"""

from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('accounts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('type', sa.String(30), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='PHP'),
        sa.Column('institution', sa.String(100), nullable=True),
        sa.Column('last_four', sa.String(4), nullable=True),
        sa.Column('fingerprint', sa.String(64), nullable=True),
        sa.Column('opening_balance', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('opening_date', sa.Date(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
    )

    op.add_column('transactions',
        sa.Column('account_id', sa.Integer(),
                  sa.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True))
    op.add_column('transactions',
        sa.Column('transfer_peer_id', sa.Integer(),
                  sa.ForeignKey('transactions.id'), nullable=True))
    op.add_column('transactions',
        sa.Column('transfer_status', sa.String(20), nullable=True))
    op.add_column('transactions',
        sa.Column('duplicate_status', sa.String(30), nullable=True))
    op.add_column('transactions',
        sa.Column('deleted_at', sa.TIMESTAMP(timezone=True), nullable=True))

    op.add_column('statements',
        sa.Column('account_id', sa.Integer(),
                  sa.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True))


def downgrade() -> None:
    op.drop_column('statements', 'account_id')
    op.drop_column('transactions', 'deleted_at')
    op.drop_column('transactions', 'duplicate_status')
    op.drop_column('transactions', 'transfer_status')
    op.drop_column('transactions', 'transfer_peer_id')
    op.drop_column('transactions', 'account_id')
    op.drop_table('accounts')

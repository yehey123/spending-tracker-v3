"""Drop opening_date from accounts — redundant; opening_balance handles the starting-point."""

from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('accounts', 'opening_date')


def downgrade() -> None:
    op.add_column('accounts', sa.Column('opening_date', sa.Date(), nullable=True))

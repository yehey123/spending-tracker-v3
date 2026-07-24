"""Add extracted_opening_balance to statements."""

from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('statements', sa.Column('extracted_opening_balance', sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('statements', 'extracted_opening_balance')

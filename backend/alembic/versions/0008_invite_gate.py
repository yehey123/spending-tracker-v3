"""Add access_requests and invite_tokens tables (E11 invite gate)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'access_requests',
        sa.Column(
            'id',
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column(
            'status',
            sa.Text(),
            nullable=False,
            server_default='pending',
        ),
        sa.Column(
            'created_at',
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )
    op.create_table(
        'invite_tokens',
        sa.Column('token_hash', sa.Text(), primary_key=True),  # SHA-256 hex
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('invite_tokens')
    op.drop_table('access_requests')

"""E18: absolute_expires_at on refresh_tokens for 30-day absolute cap."""

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"


def upgrade():
    op.add_column(
        "refresh_tokens",
        sa.Column(
            "absolute_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.execute(
        "UPDATE refresh_tokens "
        "SET absolute_expires_at = NOW() + INTERVAL '30 days' "
        "WHERE absolute_expires_at IS NULL"
    )
    op.alter_column("refresh_tokens", "absolute_expires_at", nullable=False)


def downgrade():
    op.drop_column("refresh_tokens", "absolute_expires_at")

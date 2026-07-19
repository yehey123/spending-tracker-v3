"""Add statement_kind to statements

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "statements",
        sa.Column("statement_kind", sa.String(20), nullable=True, server_default="bank_account"),
    )


def downgrade() -> None:
    op.drop_column("statements", "statement_kind")

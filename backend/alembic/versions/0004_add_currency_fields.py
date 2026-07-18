"""Add home_currency to app_settings and currency to transactions

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("home_currency", sa.String(3), nullable=True))
    op.add_column("transactions", sa.Column("currency", sa.String(3), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "currency")
    op.drop_column("app_settings", "home_currency")

"""Add AI provider configuration columns to app_settings

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("ai_provider", sa.String(20),
                  nullable=False, server_default="anthropic"))
    op.add_column("app_settings", sa.Column("ai_model", sa.String(100), nullable=True))
    op.add_column("app_settings", sa.Column("ai_api_url", sa.Text(), nullable=True))
    op.add_column("app_settings", sa.Column("gemini_api_key", sa.Text(), nullable=True))
    op.add_column("app_settings", sa.Column("google_project_id", sa.Text(), nullable=True))
    op.add_column("app_settings", sa.Column("google_location", sa.String(50), nullable=True))


def downgrade() -> None:
    for col in ("google_location", "google_project_id", "gemini_api_key",
                "ai_api_url", "ai_model", "ai_provider"):
        op.drop_column("app_settings", col)

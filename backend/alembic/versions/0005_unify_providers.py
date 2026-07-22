"""Unify OCR and AI categorization providers — drop ai_provider/ai_api_url, rename claude→anthropic

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename 'claude' → 'anthropic' everywhere provider names are stored
    op.execute("UPDATE app_settings SET ocr_provider = 'anthropic' WHERE ocr_provider = 'claude'")
    op.execute("UPDATE model_cache SET provider = 'anthropic' WHERE provider = 'claude'")

    op.drop_column("app_settings", "ai_provider")
    op.drop_column("app_settings", "ai_api_url")


def downgrade() -> None:
    op.add_column("app_settings", sa.Column("ai_api_url", sa.Text(), nullable=True))
    op.add_column("app_settings", sa.Column(
        "ai_provider", sa.String(20), nullable=False, server_default="anthropic"
    ))
    op.execute("UPDATE app_settings SET ocr_provider = 'claude' WHERE ocr_provider = 'anthropic'")
    op.execute("UPDATE model_cache SET provider = 'claude' WHERE provider = 'anthropic'")

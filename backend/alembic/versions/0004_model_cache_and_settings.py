"""model_cache table + app_settings max_output_tokens/dev_mode + statements file_hash

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(150), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(10), nullable=False, server_default="seed"),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "model_id"),
    )

    op.add_column("app_settings", sa.Column("max_output_tokens", sa.Integer(), nullable=True))
    op.add_column("app_settings", sa.Column("dev_mode", sa.Boolean(), nullable=False, server_default="false"))

    op.add_column("statements", sa.Column("file_hash", sa.String(64), nullable=True))
    op.create_index("ix_statements_file_hash", "statements", ["file_hash"])


def downgrade() -> None:
    op.drop_index("ix_statements_file_hash", table_name="statements")
    op.drop_column("statements", "file_hash")
    op.drop_column("app_settings", "dev_mode")
    op.drop_column("app_settings", "max_output_tokens")
    op.drop_table("model_cache")

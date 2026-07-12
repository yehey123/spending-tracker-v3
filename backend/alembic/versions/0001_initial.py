"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- categories ---
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.VARCHAR(100), nullable=False),
        sa.Column("color", sa.VARCHAR(7), nullable=True),
        sa.Column("icon", sa.VARCHAR(50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Functional unique index for case-insensitive name uniqueness
    op.create_index(
        "ix_categories_name",
        "categories",
        [sa.text("lower(name)")],
        unique=True,
    )

    # --- statements ---
    op.create_table(
        "statements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.VARCHAR(255), nullable=True),
        sa.Column(
            "type",
            sa.Enum("image", "pdf", name="statement_type"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum("processing", "done", "failed", name="statement_status"),
            nullable=True,
        ),
        sa.Column("ocr_provider", sa.VARCHAR(50), nullable=True),
        sa.Column(
            "uploaded_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- transactions ---
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.VARCHAR(500), nullable=False),
        sa.Column(
            "direction",
            sa.Enum("debit", "credit", name="transaction_direction"),
            nullable=True,
        ),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("statement_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"],
            ["statements.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_date", "transactions", ["date"])
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])

    # --- app_settings ---
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "ocr_provider",
            sa.VARCHAR(50),
            nullable=False,
            server_default="tesseract",
        ),
        sa.Column("anthropic_api_key", sa.Text(), nullable=True),
        sa.Column("openai_api_key", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed default settings row
    op.execute(
        "INSERT INTO app_settings (id, ocr_provider) VALUES (1, 'tesseract') ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    # Drop in reverse order to avoid FK violations
    op.drop_table("app_settings")
    op.drop_index("ix_transactions_category_id", table_name="transactions")
    op.drop_index("ix_transactions_date", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("statements")
    op.drop_index("ix_categories_name", table_name="categories")
    op.drop_table("categories")

    # Drop ENUM types
    sa.Enum(name="transaction_direction").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="statement_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="statement_type").drop(op.get_bind(), checkfirst=True)

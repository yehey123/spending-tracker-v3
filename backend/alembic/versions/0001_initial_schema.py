"""Squashed initial schema (migrations 0001–0011 consolidated)

Revision ID: 0001
Revises:
Create Date: 2026-07-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ENUMs are created by SQLAlchemy when their first containing table is created.
    # All final enum values are specified here — no ALTER TYPE ADD VALUE needed.

    # --- categories (no FK deps) ---
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.VARCHAR(100), nullable=False),
        sa.Column("color", sa.VARCHAR(7), nullable=True),
        sa.Column("icon", sa.VARCHAR(50), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("slug", sa.String(100), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["categories.id"],
            name="categories_parent_id_fkey", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categories_name", "categories", [sa.text("lower(name)")], unique=True)
    op.create_unique_constraint("uq_categories_slug", "categories", ["slug"])

    # --- app_settings (no FK deps) ---
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ocr_provider", sa.VARCHAR(50), nullable=False, server_default="tesseract"),
        sa.Column("anthropic_api_key", sa.Text(), nullable=True),
        sa.Column("openai_api_key", sa.Text(), nullable=True),
        sa.Column("home_currency", sa.String(3), nullable=True),
        sa.Column("review_before_commit", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("ai_category_confidence_auto", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("ai_category_confidence_suggest", sa.Float(), nullable=False, server_default="0.50"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- accounts (no FK deps) ---
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="PHP"),
        sa.Column("institution", sa.String(100), nullable=True),
        sa.Column("last_four", sa.String(4), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("opening_balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("opening_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- statements (FK: accounts.id) ---
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
            sa.Enum(
                "processing", "done", "failed", "pending", "ocr_failed",
                "parse_failed", "pending_categorization", "staged", "committed",
                "discarded", "expired", "error",
                name="statement_status",
            ),
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
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("file_type", sa.String(20), nullable=False, server_default="statement"),
        sa.Column("declared_total", sa.Numeric(14, 4), nullable=True),
        sa.Column("raw_ocr_text", sa.Text(), nullable=True),
        sa.Column("markdown_content", sa.Text(), nullable=True),
        sa.Column("parse_errors", postgresql.JSONB(), nullable=True),
        sa.Column("categorization_confidence", sa.Float(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"],
            name="statements_account_id_fkey", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- transactions (FK: categories, statements, accounts, self-refs) ---
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
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("transaction_origin", sa.String(20), nullable=False, server_default="uploaded"),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("parent_transaction_id", sa.Integer(), nullable=True),
        sa.Column("reversal_of", sa.Integer(), nullable=True),
        sa.Column("reversal_reason", sa.String(200), nullable=True),
        sa.Column("reversed_by", sa.Integer(), nullable=True),
        sa.Column("correction_of", sa.Integer(), nullable=True),
        sa.Column("corrected_by", sa.Integer(), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("transfer_peer_id", sa.Integer(), nullable=True),
        sa.Column("transfer_status", sa.String(20), nullable=True),
        sa.Column("duplicate_status", sa.String(30), nullable=True),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"],
            name="transactions_category_id_fkey", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"], ["statements.id"],
            name="transactions_statement_id_fkey", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_transaction_id"], ["transactions.id"],
            name="transactions_parent_transaction_id_fkey", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["reversal_of"], ["transactions.id"],
            name="transactions_reversal_of_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by"], ["transactions.id"],
            name="transactions_reversed_by_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["correction_of"], ["transactions.id"],
            name="transactions_correction_of_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["corrected_by"], ["transactions.id"],
            name="transactions_corrected_by_fkey",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"],
            name="transactions_account_id_fkey", ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["transfer_peer_id"], ["transactions.id"],
            name="transactions_transfer_peer_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_date", "transactions", ["date"])
    op.create_index("ix_transactions_category_id", "transactions", ["category_id"])

    # --- transaction_flags (FK: transactions.id CASCADE) ---
    op.create_table(
        "transaction_flags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("flag_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(20), nullable=True),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"],
            name="transaction_flags_transaction_id_fkey", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tf_tx_status", "transaction_flags", ["transaction_id", "status"])
    op.create_index("idx_tf_type_status", "transaction_flags", ["flag_type", "status"])

    # --- merchant_category_memory (FK: categories.id SET NULL) ---
    op.create_table(
        "merchant_category_memory",
        sa.Column("description_normalized", sa.String(200), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "last_used_at", sa.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"],
            name="merchant_category_memory_category_id_fkey", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("description_normalized"),
    )

    # --- audit_log (FK: transactions.id) ---
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("field", sa.String(50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column(
            "changed_at", sa.TIMESTAMP(timezone=True), nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("changed_by", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"],
            name="audit_log_transaction_id_fkey",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- investment_transactions (FK: accounts.id CASCADE, statements.id SET NULL) ---
    op.create_table(
        "investment_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("statement_id", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("shares", sa.Numeric(18, 6), nullable=False),
        sa.Column("price_per_share", sa.Numeric(18, 6), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("commission", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"],
            name="investment_transactions_account_id_fkey", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["statement_id"], ["statements.id"],
            name="investment_transactions_statement_id_fkey", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_inv_tx_account", "investment_transactions", ["account_id"])
    op.create_index("idx_inv_tx_symbol", "investment_transactions", ["symbol"])

    # --- pg_trgm extension + GIN index ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("""
        CREATE INDEX idx_transactions_description_trgm
          ON transactions USING GIN (description gin_trgm_ops)
    """)

    # --- updated_at trigger function + trigger ---
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_transactions_updated_at
          BEFORE UPDATE ON transactions
          FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # --- seed default settings row ---
    op.execute(
        "INSERT INTO app_settings (id, ocr_provider) VALUES (1, 'tesseract') ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_transactions_updated_at ON transactions")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    op.execute("DROP INDEX IF EXISTS idx_transactions_description_trgm")

    op.drop_index("idx_inv_tx_symbol", table_name="investment_transactions")
    op.drop_index("idx_inv_tx_account", table_name="investment_transactions")
    op.drop_table("investment_transactions")
    op.drop_table("audit_log")
    op.drop_table("merchant_category_memory")
    op.drop_index("idx_tf_type_status", table_name="transaction_flags")
    op.drop_index("idx_tf_tx_status", table_name="transaction_flags")
    op.drop_table("transaction_flags")
    op.drop_index("ix_transactions_category_id", table_name="transactions")
    op.drop_index("ix_transactions_date", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("statements")
    op.drop_table("accounts")
    op.drop_table("app_settings")
    op.drop_constraint("uq_categories_slug", "categories", type_="unique")
    op.drop_index("ix_categories_name", table_name="categories")
    op.drop_table("categories")

    op.execute("DROP TYPE IF EXISTS transaction_direction")
    op.execute("DROP TYPE IF EXISTS statement_status")
    op.execute("DROP TYPE IF EXISTS statement_type")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")

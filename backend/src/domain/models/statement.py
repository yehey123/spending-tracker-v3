import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class StatementType(str, enum.Enum):
    IMAGE = "image"
    PDF = "pdf"


class ParseStatus(str, enum.Enum):
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    PENDING = "pending"
    OCR_FAILED = "ocr_failed"
    PARSE_FAILED = "parse_failed"
    PENDING_CATEGORIZATION = "pending_categorization"
    STAGED = "staged"
    COMMITTED = "committed"
    DISCARDED = "discarded"
    EXPIRED = "expired"
    ERROR = "error"


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=True)
    type: Mapped[StatementType | None] = mapped_column(
        Enum("image", "pdf", name="statement_type"), nullable=True
    )
    status: Mapped[ParseStatus | None] = mapped_column(
        Enum("processing", "done", "failed", "pending", "ocr_failed", "parse_failed",
             "pending_categorization", "staged", "committed", "discarded", "expired", "error",
             name="statement_status"), nullable=True
    )
    ocr_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="statement")
    declared_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    raw_ocr_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    markdown_content: Mapped[str | None] = mapped_column(Text(), nullable=True)
    parse_errors: Mapped[dict | None] = mapped_column(JSONB(), nullable=True)
    categorization_confidence: Mapped[float | None] = mapped_column(Float(), nullable=True)

    # Added in migration 0003
    statement_kind: Mapped[str | None] = mapped_column(String(20), nullable=True, server_default="bank_account")
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Added in migration 0007
    extracted_opening_balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Added in migration 0001
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)

    # Added in migration 0010 (E13 multitenancy)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="statement")
    account: Mapped["Account | None"] = relationship("Account", back_populates="statements")

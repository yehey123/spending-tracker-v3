import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Direction(str, enum.Enum):
    DEBIT = "debit"
    CREDIT = "credit"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    direction: Mapped[Direction] = mapped_column(
        Enum("debit", "credit", name="transaction_direction"), nullable=False
    )

    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    statement_id: Mapped[int | None] = mapped_column(ForeignKey("statements.id"), nullable=True)

    # Added in migration 0004
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    # Added in migration 0006
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    transaction_origin: Mapped[str] = mapped_column(String(20), nullable=False,
                                                     server_default="uploaded")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False,
                                                  server_default="NOW()")
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False,
                                                  server_default="NOW()")

    parent_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    reversal_of: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reversed_by: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True)
    correction_of: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True)
    corrected_by: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True)

    # Added in migration 0010
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    transfer_peer_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id"), nullable=True)
    transfer_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duplicate_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    category: Mapped["Category | None"] = relationship(back_populates="transactions")
    statement: Mapped["Statement | None"] = relationship(back_populates="transactions")
    flags: Mapped[list["TransactionFlag"]] = relationship(back_populates="transaction",
                                                           cascade="all, delete-orphan")
    audit_entries: Mapped[list["AuditLog"]] = relationship(back_populates="transaction")

    # Receipt decomposition: parent/children via parent_transaction_id
    children: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys=[parent_transaction_id],
        back_populates="parent",
    )
    parent: Mapped["Transaction | None"] = relationship(
        "Transaction",
        foreign_keys=[parent_transaction_id],
        back_populates="children",
        remote_side=[id],
    )
    account: Mapped["Account | None"] = relationship(
        "Account", back_populates="transactions", foreign_keys=[account_id])

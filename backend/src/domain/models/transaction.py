import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
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
    direction: Mapped[Direction] = mapped_column(Enum(Direction), nullable=False)

    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    statement_id: Mapped[int | None] = mapped_column(ForeignKey("statements.id"), nullable=True)

    category: Mapped["Category | None"] = relationship(back_populates="transactions")
    statement: Mapped["Statement | None"] = relationship(back_populates="transactions")

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

ACCOUNT_TYPES = ('checking', 'savings', 'credit_card', 'cash', 'broker')


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, server_default="PHP")
    institution: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False,
                                                      server_default="0")
    opening_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    statements: Mapped[list["Statement"]] = relationship(back_populates="account")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account",
        foreign_keys="Transaction.account_id",
    )
    investment_transactions: Mapped[list["InvestmentTransaction"]] = relationship(
        back_populates="account", cascade="all, delete-orphan")

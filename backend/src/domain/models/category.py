from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#6B7280")
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")

    __table_args__ = (Index("ix_categories_name", func.lower(name), unique=True),)

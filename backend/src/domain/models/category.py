from sqlalchemy import Boolean, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#6B7280")
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Added in migration 0008
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True)
    slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="false")

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")
    merchant_memories: Mapped[list["MerchantCategoryMemory"]] = relationship(
        back_populates="category")

    children: Mapped[list["Category"]] = relationship(
        "Category", foreign_keys=[parent_id],
        primaryjoin="Category.parent_id == Category.id",
        back_populates="parent"
    )
    parent: Mapped["Category | None"] = relationship(
        "Category", foreign_keys=[parent_id],
        primaryjoin="Category.parent_id == Category.id",
        back_populates="children", remote_side="Category.id"
    )

    __table_args__ = (Index("ix_categories_name", func.lower(name), unique=True),)

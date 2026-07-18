from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class MerchantCategoryMemory(Base):
    __tablename__ = "merchant_category_memory"

    description_normalized: Mapped[str] = mapped_column(String(200), primary_key=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float(), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer(), nullable=False, server_default="1")
    last_used_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False,
                                                    server_default="NOW()")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False,
                                                  server_default="NOW()")

    category: Mapped["Category | None"] = relationship(back_populates="merchant_memories")

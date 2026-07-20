from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class ModelCache(Base):
    __tablename__ = "model_cache"
    __table_args__ = (UniqueConstraint("provider", "model_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False, server_default="seed")
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class AppSettings(Base):
    """Single-row settings table for OCR provider config."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    ocr_provider: Mapped[str] = mapped_column(String(50), default="tesseract")
    anthropic_api_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    openai_api_key: Mapped[str | None] = mapped_column(String(200), nullable=True)

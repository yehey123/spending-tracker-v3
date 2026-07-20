from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class AppSettings(Base):
    """Single-row settings table for OCR provider config."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    ocr_provider: Mapped[str] = mapped_column(String(50), default="tesseract")
    anthropic_api_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    openai_api_key: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Added in migration 0004
    home_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    review_before_commit: Mapped[bool] = mapped_column(Boolean(), nullable=False,
                                                        server_default="true")
    ai_category_confidence_auto: Mapped[float] = mapped_column(Float(), nullable=False,
                                                                server_default="0.85")
    ai_category_confidence_suggest: Mapped[float] = mapped_column(Float(), nullable=False,
                                                                   server_default="0.50")

    # Added in migration 0002 (post-squash)
    ai_provider: Mapped[str] = mapped_column(String(20), nullable=False,
                                              server_default="anthropic")
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_api_url: Mapped[str | None] = mapped_column(Text(), nullable=True)
    gemini_api_key: Mapped[str | None] = mapped_column(Text(), nullable=True)
    google_project_id: Mapped[str | None] = mapped_column(Text(), nullable=True)
    google_location: Mapped[str | None] = mapped_column(String(50), nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    dev_mode: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="false")

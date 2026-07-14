import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class StatementType(str, enum.Enum):
    IMAGE = "image"
    PDF = "pdf"


class ParseStatus(str, enum.Enum):
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    type: Mapped[StatementType | None] = mapped_column(
        Enum("image", "pdf", name="statement_type"), nullable=True
    )
    status: Mapped[ParseStatus | None] = mapped_column(
        Enum("processing", "done", "failed", name="statement_status"), nullable=True
    )
    ocr_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default="now()"
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="statement")

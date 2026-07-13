import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class StatementType(str, enum.Enum):
    CREDIT_CARD_SCREENSHOT = "credit_card_screenshot"
    BANK_PDF = "bank_pdf"


class ParseStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Statement(Base):
    __tablename__ = "statements"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    type: Mapped[StatementType] = mapped_column(Enum(StatementType), nullable=False)
    status: Mapped[ParseStatus] = mapped_column(Enum(ParseStatus), default=ParseStatus.PENDING)
    ocr_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="statement")

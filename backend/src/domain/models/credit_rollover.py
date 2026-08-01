import uuid
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from src.db.base import Base


class CreditRollover(Base):
    __tablename__ = "credit_rollovers"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )
    period: Mapped[date] = mapped_column(primary_key=True)
    credits_given: Mapped[int] = mapped_column(Integer, nullable=False)

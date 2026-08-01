"""ORM model for the invite_tokens table (E11 invite gate)."""

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class InviteToken(Base):
    __tablename__ = "invite_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)  # SHA-256 hex
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

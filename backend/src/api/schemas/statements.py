from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class StatementOut(BaseModel):
    id: int
    filename: str
    type: str
    status: str
    ocr_provider: str | None
    transaction_count: int
    uploaded_at: datetime
    error_message: str | None = None
    declared_total: Decimal | None = None
    model_config = ConfigDict(from_attributes=True)

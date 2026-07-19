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
    account_id: int | None = None
    account_created: bool = False
    statement_kind: str | None = "bank_account"
    model_config = ConfigDict(from_attributes=True)


class ReceiptOut(BaseModel):
    id: int
    filename: str
    status: str
    uploaded_at: datetime
    declared_total: Decimal | None = None
    suggested_parent_ids: list[int] = []
    model_config = ConfigDict(from_attributes=True)

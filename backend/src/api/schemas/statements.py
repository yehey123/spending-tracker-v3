from pydantic import BaseModel, ConfigDict
from datetime import datetime


class StatementOut(BaseModel):
    id: int
    filename: str
    type: str
    status: str
    ocr_provider: str | None
    transaction_count: int
    uploaded_at: datetime
    error_message: str | None = None
    model_config = ConfigDict(from_attributes=True)

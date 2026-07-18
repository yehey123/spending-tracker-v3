from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class TransactionCreate(BaseModel):
    date: datetime
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str = Field(min_length=1, max_length=500)
    direction: Literal["debit", "credit"]
    category_id: int | None = None
    currency: str | None = None


class TransactionPatch(BaseModel):
    category_id: int | None = None
    description: str | None = Field(default=None, min_length=1, max_length=500)
    currency: str | None = None


class CategoryInline(BaseModel):
    id: int
    name: str
    color: str
    model_config = ConfigDict(from_attributes=True)


class TransactionOut(BaseModel):
    id: int
    date: datetime
    amount: Decimal
    description: str
    direction: str
    category_id: int | None
    category: CategoryInline | None
    statement_id: int | None
    currency: str | None
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("amount")
    def serialize_amount(self, v: Decimal) -> str:
        """Return amount as a normalized decimal string (removes trailing zeros)."""
        return str(v.normalize())

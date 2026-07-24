from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class TransactionCreate(BaseModel):
    date: datetime
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    description: str = Field(min_length=1, max_length=500)
    direction: Literal["debit", "credit"]
    category_id: int | None = None
    currency: str | None = None  # ISO-4217 3-letter code; null = home currency

    @field_validator('date')
    @classmethod
    def make_date_naive(cls, v: datetime) -> datetime:
        if v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


class TransactionPatch(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    date: datetime | None = None

    @field_validator('date')
    @classmethod
    def make_date_naive(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v
    description: str | None = Field(default=None, min_length=1, max_length=500)
    direction: Literal["debit", "credit"] | None = None
    category_id: int | None = None
    currency: str | None = None


class ReverseRequest(BaseModel):
    ids: list[int] = Field(min_length=1)
    reason: str
    notes: str | None = None

    @field_validator('reason')
    @classmethod
    def reason_must_be_valid(cls, v: str) -> str:
        valid = {'duplicate', 'bank_reversal', 'user_error',
                 'receipt_superseded', 'user_correction', 'other'}
        if v not in valid:
            raise ValueError(f"reason must be one of {valid}")
        return v


class ParentPatch(BaseModel):
    parent_transaction_id: int | None = None


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
    currency: str | None = None
    status: str | None = None
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("amount")
    def serialize_amount(self, v: Decimal) -> str:
        return str(v.normalize())


class TransactionPatchResult(BaseModel):
    id: int
    re_categorized: int = 0
    reversal_id: int | None = None
    correction_id: int | None = None


class AuditLogOut(BaseModel):
    id: int
    transaction_id: int
    field: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: str
    reason: str | None = None
    model_config = ConfigDict(from_attributes=True)

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class CategoryBreakdown(BaseModel):
    category_id: int | None
    category_name: str
    color: str
    amount: Decimal
    percent: float


class ByCategoryResponse(BaseModel):
    month: str
    total_debit: Decimal
    breakdown: list[CategoryBreakdown]
    display_currency: str | None = None
    unconverted_count: int = 0
    totals_available: bool = True


class MonthCashFlow(BaseModel):
    month: str
    total_credit: Decimal
    total_debit: Decimal
    net: Decimal


class CashFlowResponse(BaseModel):
    months: list[MonthCashFlow]
    display_currency: str | None = None
    unconverted_count: int = 0
    totals_available: bool = True

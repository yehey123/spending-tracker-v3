from pydantic import BaseModel
from decimal import Decimal


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


class MonthCashFlow(BaseModel):
    month: str
    total_credit: Decimal
    total_debit: Decimal
    net: Decimal


class CashFlowResponse(BaseModel):
    months: list[MonthCashFlow]

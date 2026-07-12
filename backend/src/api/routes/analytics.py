"""Analytics routes: by-category and cash-flow summaries."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from src.db.session import get_db
from src.domain.models.transaction import Transaction
from src.domain.models.category import Category
from src.api.schemas.analytics import (
    ByCategoryResponse,
    CategoryBreakdown,
    CashFlowResponse,
    MonthCashFlow,
)

router = APIRouter()


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    """Return (first_day, first_day_of_next_month) for a YYYY-MM string."""
    year, mon = int(month[:4]), int(month[5:7])
    first_day = datetime(year, mon, 1, tzinfo=timezone.utc)
    if mon == 12:
        next_year, next_mon = year + 1, 1
    else:
        next_year, next_mon = year, mon + 1
    first_day_next = datetime(next_year, next_mon, 1, tzinfo=timezone.utc)
    return first_day, first_day_next


@router.get("/by-category", response_model=ByCategoryResponse)
async def by_category(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
):
    """Spending (debits only) grouped by category for the given month."""
    first_day, first_day_next = _month_bounds(month)

    # SUM(amount) GROUP BY category_id for debits in the month
    rows_result = await db.execute(
        select(Transaction.category_id, func.sum(Transaction.amount).label("total"))
        .where(
            Transaction.direction == "debit",
            Transaction.date >= first_day,
            Transaction.date < first_day_next,
        )
        .group_by(Transaction.category_id)
    )
    rows = rows_result.all()

    total_debit: Decimal = sum((row.total for row in rows), Decimal("0"))

    # Fetch category info for all non-null category_ids
    category_ids = [row.category_id for row in rows if row.category_id is not None]
    cats: dict[int, Category] = {}
    if category_ids:
        cat_result = await db.execute(
            select(Category).where(Category.id.in_(category_ids))
        )
        for cat in cat_result.scalars().all():
            cats[cat.id] = cat

    breakdown: list[CategoryBreakdown] = []
    for row in rows:
        amount = row.total or Decimal("0")
        percent = float(amount / total_debit * 100) if total_debit else 0.0
        if row.category_id is not None and row.category_id in cats:
            cat = cats[row.category_id]
            breakdown.append(
                CategoryBreakdown(
                    category_id=row.category_id,
                    category_name=cat.name,
                    color=cat.color,
                    amount=amount,
                    percent=round(percent, 1),
                )
            )
        else:
            breakdown.append(
                CategoryBreakdown(
                    category_id=None,
                    category_name="Uncategorized",
                    color="#6B7280",
                    amount=amount,
                    percent=round(percent, 1),
                )
            )

    return ByCategoryResponse(month=month, total_debit=total_debit, breakdown=breakdown)


@router.get("/cash-flow", response_model=CashFlowResponse)
async def cash_flow(
    months: int = Query(default=6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
):
    """Monthly credit/debit totals for the last N calendar months."""
    now = datetime.now(tz=timezone.utc)

    # Build list of (year, month) going back `months` months inclusive of current
    month_list: list[tuple[int, int]] = []
    year, mon = now.year, now.month
    for _ in range(months):
        month_list.append((year, mon))
        mon -= 1
        if mon == 0:
            mon = 12
            year -= 1
    month_list.reverse()  # chronological order

    result_months: list[MonthCashFlow] = []
    for year, mon in month_list:
        month_str = f"{year:04d}-{mon:02d}"
        first_day = datetime(year, mon, 1, tzinfo=timezone.utc)
        if mon == 12:
            next_year, next_mon = year + 1, 1
        else:
            next_year, next_mon = year, mon + 1
        first_day_next = datetime(next_year, next_mon, 1, tzinfo=timezone.utc)

        # Sum credit
        credit_result = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.direction == "credit",
                Transaction.date >= first_day,
                Transaction.date < first_day_next,
            )
        )
        total_credit = Decimal(str(credit_result.scalar()))

        # Sum debit
        debit_result = await db.execute(
            select(func.coalesce(func.sum(Transaction.amount), 0))
            .where(
                Transaction.direction == "debit",
                Transaction.date >= first_day,
                Transaction.date < first_day_next,
            )
        )
        total_debit = Decimal(str(debit_result.scalar()))

        result_months.append(
            MonthCashFlow(
                month=month_str,
                total_credit=total_credit,
                total_debit=total_debit,
                net=total_credit - total_debit,
            )
        )

    return CashFlowResponse(months=result_months)

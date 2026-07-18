"""Analytics routes: by-category and cash-flow summaries with optional currency conversion."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.analytics import (
    ByCategoryResponse,
    CashFlowResponse,
    CategoryBreakdown,
    MonthCashFlow,
)
from src.db.session import get_db
from src.domain.models.app_settings import AppSettings
from src.domain.models.category import Category
from src.domain.models.transaction import Transaction
from src.domain.services.exchange_rate import exchange_rate_service

router = APIRouter()


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    """Return (first_day, first_day_of_next_month) for a YYYY-MM string (tz-naive)."""
    year, mon = int(month[:4]), int(month[5:7])
    first_day = datetime(year, mon, 1)
    if mon == 12:
        next_year, next_mon = year + 1, 1
    else:
        next_year, next_mon = year, mon + 1
    return first_day, datetime(next_year, next_mon, 1)


async def _get_home_currency(db: AsyncSession) -> str | None:
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    return row.home_currency if row else None


async def _convert_amount(
    amount: Decimal,
    from_currency: str | None,
    to_currency: str,
    date_str: str,
    unconverted_count_ref: list[int],
    home_currency: str | None,
) -> Decimal:
    """Convert amount from from_currency to to_currency. Null currency = home currency."""
    effective_from = from_currency or home_currency
    if effective_from is None or effective_from == to_currency:
        return amount
    rate = await exchange_rate_service.get_rate(date_str, effective_from, to_currency)
    if rate is None:
        unconverted_count_ref[0] += 1
        return amount  # return unconverted
    return amount * Decimal(str(rate))


@router.get("/by-category", response_model=ByCategoryResponse)
async def by_category(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    display_currency: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Spending (debits only) grouped by category for the given month.

    If display_currency is provided, converts all amounts. If home_currency
    is set in settings, uses that as default. If neither, returns amounts
    in original currencies with totals_available=False.
    """
    first_day, first_day_next = _month_bounds(month)
    home_currency = await _get_home_currency(db)
    effective_display_currency = display_currency or home_currency

    # Fetch individual rows (not aggregated) so we can get per-row currency
    rows_result = await db.execute(
        select(
            Transaction.category_id,
            Transaction.amount,
            Transaction.currency,
            Transaction.date,
        )
        .where(
            Transaction.direction == "debit",
            Transaction.date >= first_day,
            Transaction.date < first_day_next,
            Transaction.status == "active",
            Transaction.reversed_by.is_(None),
            Transaction.reversal_of.is_(None),
        )
    )
    rows = rows_result.all()

    # Aggregate with optional currency conversion
    category_totals: dict[int | None, Decimal] = defaultdict(lambda: Decimal("0"))
    unconverted_ref = [0]  # mutable reference for counter

    for row in rows:
        date_str = row.date.strftime("%Y-%m-%d") if row.date else "2000-01-01"
        if effective_display_currency:
            amount = await _convert_amount(
                row.amount, row.currency, effective_display_currency,
                date_str, unconverted_ref, home_currency
            )
        else:
            amount = row.amount
        category_totals[row.category_id] += amount

    total_debit = sum(category_totals.values(), Decimal("0"))
    unconverted_count = unconverted_ref[0]

    # Fetch category info
    category_ids = [cid for cid in category_totals.keys() if cid is not None]
    cats: dict[int, Category] = {}
    if category_ids:
        cat_result = await db.execute(select(Category).where(Category.id.in_(category_ids)))
        for cat in cat_result.scalars().all():
            cats[cat.id] = cat

    breakdown: list[CategoryBreakdown] = []
    for cat_id, amount in category_totals.items():
        percent = float(amount / total_debit * 100) if total_debit else 0.0
        if cat_id is not None and cat_id in cats:
            cat = cats[cat_id]
            breakdown.append(CategoryBreakdown(
                category_id=cat_id,
                category_name=cat.name,
                color=cat.color or "#6B7280",
                amount=amount,
                percent=round(percent, 1),
            ))
        else:
            breakdown.append(CategoryBreakdown(
                category_id=None,
                category_name="Uncategorized",
                color="#6B7280",
                amount=amount,
                percent=round(percent, 1),
            ))

    totals_available = effective_display_currency is not None

    return ByCategoryResponse(
        month=month,
        total_debit=total_debit,
        breakdown=breakdown,
        display_currency=effective_display_currency,
        unconverted_count=unconverted_count,
        totals_available=totals_available,
    )


@router.get("/cash-flow", response_model=CashFlowResponse)
async def cash_flow(
    months: int = Query(default=6, ge=1, le=24),
    display_currency: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Monthly credit/debit totals for the last N calendar months."""
    now = datetime.now()
    home_currency = await _get_home_currency(db)
    effective_display_currency = display_currency or home_currency

    month_list: list[tuple[int, int]] = []
    year, mon = now.year, now.month
    for _ in range(months):
        month_list.append((year, mon))
        mon -= 1
        if mon == 0:
            mon = 12
            year -= 1
    month_list.reverse()

    result_months: list[MonthCashFlow] = []
    total_unconverted = 0

    for year, mon in month_list:
        month_str = f"{year:04d}-{mon:02d}"
        first_day = datetime(year, mon, 1)
        if mon == 12:
            next_year, next_mon = year + 1, 1
        else:
            next_year, next_mon = year, mon + 1
        first_day_next = datetime(next_year, next_mon, 1)

        rows_result = await db.execute(
            select(
                Transaction.direction,
                Transaction.amount,
                Transaction.currency,
                Transaction.date,
            )
            .where(
                Transaction.date >= first_day,
                Transaction.date < first_day_next,
                Transaction.status == "active",
                Transaction.reversed_by.is_(None),
                Transaction.reversal_of.is_(None),
            )
        )
        rows = rows_result.all()

        total_credit = Decimal("0")
        total_debit = Decimal("0")
        month_unconverted_ref = [0]

        for row in rows:
            date_str = row.date.strftime("%Y-%m-%d") if row.date else f"{year:04d}-{mon:02d}-01"
            if effective_display_currency:
                amount = await _convert_amount(
                    row.amount, row.currency, effective_display_currency,
                    date_str, month_unconverted_ref, home_currency
                )
            else:
                amount = row.amount

            direction = row.direction.value if hasattr(row.direction, 'value') else row.direction
            if direction == "credit":
                total_credit += amount
            else:
                total_debit += amount

        total_unconverted += month_unconverted_ref[0]

        result_months.append(MonthCashFlow(
            month=month_str,
            total_credit=total_credit,
            total_debit=total_debit,
            net=total_credit - total_debit,
        ))

    totals_available = effective_display_currency is not None

    return CashFlowResponse(
        months=result_months,
        display_currency=effective_display_currency,
        unconverted_count=total_unconverted,
        totals_available=totals_available,
    )

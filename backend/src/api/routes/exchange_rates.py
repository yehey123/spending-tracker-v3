"""Exchange rates API routes."""

import datetime

from fastapi import APIRouter, HTTPException

from src.api.schemas.exchange_rates import PrefetchIn, PrefetchOut, SupportedCurrenciesOut
from src.domain.services.exchange_rate import exchange_rate_service

router = APIRouter()


@router.get("/supported", response_model=SupportedCurrenciesOut)
async def get_supported_currencies() -> SupportedCurrenciesOut:
    """Return a map of supported ISO-4217 currency codes and their names."""
    currencies = await exchange_rate_service.get_supported_currencies()
    return SupportedCurrenciesOut(currencies=currencies)


@router.post("/prefetch", response_model=PrefetchOut)
async def prefetch_rates(body: PrefetchIn) -> PrefetchOut:
    """Prefetch and cache exchange rates for a date range.

    Validates:
    - from_currency != to_currency
    - Dates in YYYY-MM-DD format
    - start_date <= end_date
    - Date range <= 10 years
    """
    if body.from_currency == body.to_currency:
        raise HTTPException(
            status_code=422,
            detail="from_currency and to_currency must be different.",
        )

    try:
        start = datetime.date.fromisoformat(body.start_date)
        end = datetime.date.fromisoformat(body.end_date)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="start_date and end_date must be in YYYY-MM-DD format.",
        ) from exc

    if start > end:
        raise HTTPException(
            status_code=422,
            detail="start_date must be on or before end_date.",
        )

    ten_years = datetime.timedelta(days=365 * 10)
    if (end - start) > ten_years:
        raise HTTPException(
            status_code=422,
            detail="Date range must not exceed 10 years.",
        )

    result = await exchange_rate_service.prefetch_range(
        base=body.from_currency,
        quote=body.to_currency,
        start=body.start_date,
        end=body.end_date,
    )
    return PrefetchOut(**result)

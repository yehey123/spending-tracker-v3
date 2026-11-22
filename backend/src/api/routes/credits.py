"""Credit quota read endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user
from src.db.session import get_db
from src.domain.models.user import User
from src.domain.services.credits import _get_monthly_grant_amount, _get_weights, get_balance

router = APIRouter()


@router.get("/balance")
async def credit_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current credit balance and config for the authenticated user."""
    balance = await get_balance(user_id=current_user.id, db=db)
    weights = await _get_weights(db)
    monthly = await _get_monthly_grant_amount(db)
    return {
        "balance": balance,
        "monthly_grant": monthly,
        "weights": weights,
    }

"""Investment transaction list for a broker account."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.domain.models.account import Account
from src.domain.models.investment_transaction import InvestmentTransaction

router = APIRouter()


@router.get("")
async def list_investment_transactions(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    if acc.type != 'broker':
        raise HTTPException(422, "Account is not a broker account")

    result = await db.execute(
        select(InvestmentTransaction)
        .where(InvestmentTransaction.account_id == account_id)
        .order_by(InvestmentTransaction.date.desc())
    )
    txns = result.scalars().all()
    return [
        {
            "id": t.id,
            "date": t.date.isoformat(),
            "symbol": t.symbol,
            "direction": t.direction,
            "shares": str(t.shares),
            "price_per_share": str(t.price_per_share),
            "amount": str(t.amount),
            "commission": str(t.commission) if t.commission else None,
            "currency": t.currency,
        }
        for t in txns
    ]

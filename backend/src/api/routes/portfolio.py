"""Portfolio holdings: group investment_transactions by symbol, compute cost basis."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.domain.models.account import Account
from src.domain.models.investment_transaction import InvestmentTransaction

router = APIRouter()


@router.get("")
async def get_portfolio(
    account_id: int,
    include_closed: bool = False,
    db: AsyncSession = Depends(get_db),
):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    if acc.type != 'broker':
        raise HTTPException(422, "Account is not a broker account")

    result = await db.execute(
        select(
            InvestmentTransaction.symbol,
            InvestmentTransaction.currency,
            func.sum(
                case(
                    (InvestmentTransaction.direction == 'buy', InvestmentTransaction.shares),
                    else_=-InvestmentTransaction.shares,
                )
            ).label('net_shares'),
            func.sum(
                case(
                    (InvestmentTransaction.direction == 'buy', InvestmentTransaction.amount),
                    else_=Decimal('0'),
                )
            ).label('total_cost'),
            func.sum(
                case(
                    (InvestmentTransaction.direction == 'buy', InvestmentTransaction.shares),
                    else_=Decimal('0'),
                )
            ).label('total_buy_shares'),
        )
        .where(InvestmentTransaction.account_id == account_id)
        .group_by(InvestmentTransaction.symbol, InvestmentTransaction.currency)
    )
    rows = result.all()

    holdings = []
    for row in rows:
        net_shares = row.net_shares or Decimal('0')
        total_cost = row.total_cost or Decimal('0')
        total_buy_shares = row.total_buy_shares or Decimal('0')

        if net_shares <= 0 and not include_closed:
            continue

        avg_cost = total_cost / total_buy_shares if total_buy_shares else Decimal('0')
        holdings.append({
            "symbol": row.symbol,
            "currency": row.currency,
            "shares_held": str(net_shares),
            "avg_cost_per_share": str(avg_cost),
            "total_cost_basis": str(net_shares * avg_cost),
            "last_price": None,
        })

    return {
        "account_id": account_id,
        "holdings": holdings,
        "last_price_note": "Live price feed is a future feature",
    }

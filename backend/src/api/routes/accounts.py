"""Account CRUD + fingerprint-based deduplication + transfer detection trigger."""

import hashlib
import hmac
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.session import get_db
from src.domain.models.account import Account, ACCOUNT_TYPES
from src.domain.models.transaction import Transaction

router = APIRouter()


def compute_fingerprint(account_number: str) -> str:
    secret = settings.app_secret
    if not secret or len(secret) < 32:
        raise ValueError("APP_SECRET must be set and at least 32 characters")
    return hmac.new(secret.encode(), account_number.encode(), hashlib.sha256).hexdigest()


class AccountCreate(BaseModel):
    name: str
    type: str
    currency: str = "PHP"
    institution: str | None = None
    account_number: str | None = None
    opening_balance: float = 0
    opening_date: date


class AccountUpdate(BaseModel):
    name: str | None = None
    currency: str | None = None
    institution: str | None = None
    is_active: bool | None = None


def _account_dict(acc: Account, current_balance: Decimal) -> dict:
    return {
        "id": acc.id,
        "name": acc.name,
        "type": acc.type,
        "currency": acc.currency,
        "institution": acc.institution,
        "last_four": acc.last_four,
        "opening_balance": str(acc.opening_balance),
        "opening_date": acc.opening_date.isoformat(),
        "is_active": acc.is_active,
        "current_balance": str(current_balance),
    }


@router.get("")
async def list_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account).where(Account.is_active == True))
    accounts = result.scalars().all()
    out = []
    for acc in accounts:
        balance_result = await db.execute(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (Transaction.direction == 'credit', Transaction.amount),
                            else_=-Transaction.amount,
                        )
                    ),
                    Decimal('0'),
                )
            ).where(
                Transaction.account_id == acc.id,
                Transaction.date >= acc.opening_date,
                Transaction.status == 'active',
                Transaction.reversed_by.is_(None),
                Transaction.reversal_of.is_(None),
                Transaction.deleted_at.is_(None),
            )
        )
        txn_delta = balance_result.scalar() or Decimal('0')
        out.append(_account_dict(acc, acc.opening_balance + txn_delta))
    return out


@router.post("", status_code=201)
async def create_account(body: AccountCreate, db: AsyncSession = Depends(get_db)):
    if body.type not in ACCOUNT_TYPES:
        raise HTTPException(422, f"Invalid account type. Valid: {ACCOUNT_TYPES}")

    fingerprint = None
    last_four = None
    if body.account_number:
        last_four = body.account_number[-4:]
        try:
            fingerprint = compute_fingerprint(body.account_number)
        except ValueError as e:
            raise HTTPException(500, str(e))

    acc = Account(
        name=body.name,
        type=body.type,
        currency=body.currency,
        institution=body.institution,
        last_four=last_four,
        fingerprint=fingerprint,
        opening_balance=Decimal(str(body.opening_balance)),
        opening_date=body.opening_date,
    )
    db.add(acc)
    await db.commit()
    await db.refresh(acc)
    return {
        "id": acc.id,
        "name": acc.name,
        "type": acc.type,
        "currency": acc.currency,
        "institution": acc.institution,
        "last_four": acc.last_four,
        "fingerprint": None,  # never returned
        "opening_balance": str(acc.opening_balance),
        "opening_date": acc.opening_date.isoformat(),
        "is_active": acc.is_active,
    }


@router.patch("/{account_id}")
async def update_account(
    account_id: int, body: AccountUpdate, db: AsyncSession = Depends(get_db)
):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(acc, field, value)
    await db.commit()
    await db.refresh(acc)
    return _account_dict(acc, acc.opening_balance)


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")
    await db.execute(
        update(Transaction)
        .where(Transaction.account_id == account_id)
        .values(account_id=None)
    )
    acc.is_active = False
    await db.commit()


@router.get("/{account_id}/balance")
async def get_account_balance(account_id: int, db: AsyncSession = Depends(get_db)):
    acc = await db.get(Account, account_id)
    if not acc:
        raise HTTPException(404, "Account not found")

    if acc.type == 'broker':
        from sqlalchemy import func, select
        from src.domain.models.investment_transaction import InvestmentTransaction
        result = await db.execute(
            select(func.coalesce(func.sum(InvestmentTransaction.amount), 0))
            .where(
                InvestmentTransaction.account_id == account_id,
                InvestmentTransaction.direction == 'buy',
            )
        )
        cost_basis = result.scalar() or Decimal('0')
        return {"type": "broker", "cost_basis": str(cost_basis), "current_value": None}

    balance_result = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.direction == 'credit', Transaction.amount),
                        else_=-Transaction.amount,
                    )
                ),
                Decimal('0'),
            )
        ).where(
            Transaction.account_id == account_id,
            Transaction.date >= acc.opening_date,
            Transaction.status == 'active',
            Transaction.reversed_by.is_(None),
            Transaction.reversal_of.is_(None),
            Transaction.deleted_at.is_(None),
        )
    )
    txn_delta = balance_result.scalar() or Decimal('0')
    return {
        "type": acc.type,
        "opening_balance": str(acc.opening_balance),
        "current_balance": str(acc.opening_balance + txn_delta),
    }


@router.post("/transfer-detect")
async def trigger_transfer_detection(db: AsyncSession = Depends(get_db)):
    from src.domain.services.transfer_detector import detect_transfers
    pairs = await detect_transfers(None, db)
    await db.commit()
    return {"pairs_flagged": pairs}

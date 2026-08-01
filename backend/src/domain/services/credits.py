"""Credit quota domain service.

All balance mutations are append-only (INSERT into credit_ledger only).
Never UPDATE or DELETE credit_ledger rows — it is a financial audit trail.
"""
from __future__ import annotations

import uuid
import logging
from datetime import date

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.credit_ledger import CreditLedger
from src.domain.models.credit_rollover import CreditRollover
from src.domain.models.db_config import DbConfig

logger = logging.getLogger(__name__)


class InsufficientCredits(Exception):
    def __init__(self, balance: int, cost: int):
        self.balance = balance
        self.cost = cost
        super().__init__(f"Insufficient credits: balance={balance}, cost={cost}")


async def _get_weights(db: AsyncSession) -> dict[str, int]:
    row = await db.get(DbConfig, "credit_weights")
    if row is None:
        return {"tesseract": 0, "anthropic": 3, "openai": 3, "gemini": 2, "vertex": 2}
    return row.value


async def _get_monthly_grant_amount(db: AsyncSession) -> int:
    row = await db.get(DbConfig, "monthly_grant")
    if row is None:
        return 30
    try:
        return int(row.value)
    except (TypeError, ValueError):
        return 30


async def get_balance(user_id: uuid.UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.coalesce(func.sum(CreditLedger.amount), 0))
        .where(CreditLedger.user_id == user_id)
    )
    return int(result.scalar_one())


async def atomic_debit(
    user_id: uuid.UUID,
    provider: str,
    statement_id: int | str,
    db: AsyncSession,
) -> int:
    """Atomically debit credits for one OCR call. Returns credits debited (0 for Tesseract).

    Uses pg_advisory_xact_lock to serialize concurrent debits for the same user.
    The lock is released automatically when the transaction commits or rolls back.

    Raises InsufficientCredits if balance < cost. Caller must catch this and
    fall back to TesseractProvider.
    """
    weights = await _get_weights(db)
    cost = weights.get(provider.lower(), 0)
    if cost == 0:
        return 0

    # Deterministic int64 key — stable across workers (not hash() which is PYTHONHASHSEED-random)
    user_lock_key = user_id.int & 0x7FFFFFFFFFFFFFFF
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": user_lock_key})

    balance = await get_balance(user_id, db)
    if balance < cost:
        raise InsufficientCredits(balance=balance, cost=cost)

    idempotency_key = f"debit:{statement_id}:{provider}"
    entry = CreditLedger(
        user_id=user_id,
        amount=-cost,
        reason=f"ocr_{provider.lower()}",
        ref_id=str(statement_id),
        idempotency_key=idempotency_key,
    )
    db.add(entry)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        logger.warning("Duplicate debit key %s — already debited, skipping", idempotency_key)
        return 0

    logger.info("Debited %d credits from user %s for %s (statement=%s)",
                cost, user_id, provider, statement_id)
    return cost


async def grant_monthly(
    user_id: uuid.UUID,
    period: date,
    db: AsyncSession,
) -> bool:
    """Grant monthly credits for a user + period. Idempotent — safe to call multiple times.

    Returns True if credits were granted, False if already granted this period.
    """
    amount = await _get_monthly_grant_amount(db)
    idempotency_key = f"monthly_grant:{user_id}:{period.strftime('%Y-%m')}"

    rollover = CreditRollover(
        user_id=user_id,
        period=period,
        credits_given=amount,
    )
    db.add(rollover)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        logger.info("Monthly grant for user %s period %s already issued — skipping", user_id, period)
        return False

    entry = CreditLedger(
        user_id=user_id,
        amount=amount,
        reason="monthly_grant",
        idempotency_key=idempotency_key,
    )
    db.add(entry)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return False

    logger.info("Granted %d credits to user %s for period %s", amount, user_id, period)
    return True

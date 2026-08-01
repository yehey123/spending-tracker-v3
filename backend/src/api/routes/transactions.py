"""Transactions CRUD routes with filtering, reversal, and pagination."""

from __future__ import annotations

import base64
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas.transactions import (
    AuditLogOut,
    ParentPatch,
    ReverseRequest,
    TransactionCreate,
    TransactionOut,
    TransactionPatch,
    TransactionPatchResult,
)
from src.core import cache
from src.core.deps import get_current_user
from src.db.session import get_db
from src.domain.models.audit_log import AuditLog
from src.domain.models.category import Category
from src.domain.models.transaction import Transaction
from src.domain.models.user import User

router = APIRouter()

FINANCIAL_FIELDS = {'amount', 'date', 'direction', 'description', 'currency'}


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    year, mon = int(month[:4]), int(month[5:7])
    first_day = datetime(year, mon, 1)
    if mon == 12:
        next_year, next_mon = year + 1, 1
    else:
        next_year, next_mon = year, mon + 1
    return first_day, datetime(next_year, next_mon, 1)


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    category_id: int | None = Query(default=None),
    direction: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List transactions (active only by default); ordered by date DESC."""
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.category))
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.date.desc())
        .limit(limit)
        .offset(offset)
    )
    # By default only return active transactions (not reversed or staged)
    if status is not None:
        stmt = stmt.where(Transaction.status == status)
    else:
        stmt = stmt.where(Transaction.status == 'active')
    # Exclude reversal rows and reversed rows from default view
    stmt = stmt.where(Transaction.reversed_by.is_(None))
    stmt = stmt.where(Transaction.reversal_of.is_(None))

    if month is not None:
        first_day, first_day_next = _month_bounds(month)
        stmt = stmt.where(Transaction.date >= first_day, Transaction.date < first_day_next)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if direction is not None:
        stmt = stmt.where(Transaction.direction == direction)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/search", response_model=list[TransactionOut])
async def search_transactions(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    linkable_only: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full-text search over transaction descriptions using pg_trgm similarity."""
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.category))
        .where(
            Transaction.user_id == current_user.id,
            Transaction.status == 'active',
            Transaction.reversed_by.is_(None),
            Transaction.reversal_of.is_(None),
            or_(
                func.similarity(Transaction.description, q) > 0.3,
                Transaction.description.ilike(f'%{q}%'),
            ),
        )
    )

    if linkable_only:
        stmt = stmt.where(Transaction.parent_transaction_id.is_(None))

    if cursor is not None:
        try:
            payload = json.loads(base64.b64decode(cursor).decode())
            cursor_date = datetime.fromisoformat(payload['date'])
            cursor_id = int(payload['id'])
            stmt = stmt.where(
                tuple_(Transaction.date, Transaction.id) < tuple_(cursor_date, cursor_id)
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    stmt = stmt.order_by(Transaction.date.desc(), Transaction.id.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(
    body: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a manual transaction (no statement source)."""
    if body.category_id is not None:
        cat_result = await db.execute(select(Category).where(Category.id == body.category_id))
        if cat_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail=f"Category {body.category_id} not found.")

    tx = Transaction(
        date=body.date,
        amount=body.amount,
        description=body.description,
        direction=body.direction,
        category_id=body.category_id,
        currency=body.currency,
        statement_id=None,
        status='active',
        transaction_origin='manual',
        user_id=current_user.id,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)
    cache.clear_for_user(current_user.id)

    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.category))
        .where(Transaction.id == tx.id)
    )
    return result.scalar_one()


@router.patch("/{id}", response_model=TransactionPatchResult)
async def patch_transaction(
    id: int,
    body: TransactionPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partial update — financial changes trigger reversal+correction on committed transactions."""
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.category))
        .where(Transaction.id == id, Transaction.user_id == current_user.id)
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    changed = body.model_dump(exclude_unset=True)
    financial_changes = {k: v for k, v in changed.items() if k in FINANCIAL_FIELDS}
    category_change = changed.get('category_id')

    re_categorized = 0
    reversal_id = None
    correction_id = None

    tx_status = tx.status.value if hasattr(tx.status, 'value') else tx.status

    if tx_status == 'staged':
        # Staged: direct update, no reversal, no audit log
        for field, value in changed.items():
            setattr(tx, field, value)
        await db.commit()
        cache.clear_for_user(current_user.id)
        result2 = await db.execute(
            select(Transaction).options(selectinload(Transaction.category)).where(Transaction.id == id)
        )
        updated = result2.scalar_one()
        return TransactionPatchResult(id=updated.id)

    # Committed transaction path
    correction = None
    if financial_changes:
        tx_direction = tx.direction.value if hasattr(tx.direction, 'value') else tx.direction
        # Strip timezone info: asyncpg may return tz-aware datetimes for TIMESTAMP WITHOUT TIME ZONE
        tx_date = tx.date.replace(tzinfo=None) if tx.date and tx.date.tzinfo else tx.date
        reversal = Transaction(
            date=tx_date,
            amount=tx.amount,
            description=tx.description,
            direction='credit' if tx_direction == 'debit' else 'debit',
            category_id=tx.category_id,
            statement_id=tx.statement_id,
            currency=tx.currency,
            status='active',
            transaction_origin=tx.transaction_origin if isinstance(tx.transaction_origin, str) else tx.transaction_origin.value,
            reversal_of=tx.id,
            reversal_reason='user_correction',
            user_id=current_user.id,
        )
        db.add(reversal)
        await db.flush()

        correction_data = {
            'date': tx_date,
            'amount': tx.amount,
            'description': tx.description,
            'direction': tx.direction,
            'category_id': tx.category_id,
            'statement_id': tx.statement_id,
            'currency': tx.currency,
            'status': 'active',
            'transaction_origin': tx.transaction_origin if isinstance(tx.transaction_origin, str) else tx.transaction_origin.value,
            'correction_of': tx.id,
            'user_id': current_user.id,
        }
        correction_data.update(financial_changes)
        correction = Transaction(**correction_data)
        db.add(correction)
        await db.flush()

        tx.reversed_by = reversal.id
        tx.corrected_by = correction.id
        reversal_id = reversal.id
        correction_id = correction.id

    if 'category_id' in changed:
        target = correction if financial_changes else tx
        old_value = str(target.category_id) if target.category_id else None
        new_cat_id = changed.get('category_id')
        target.category_id = new_cat_id

        db.add(AuditLog(
            transaction_id=target.id,
            field='category_id',
            old_value=old_value,
            new_value=str(new_cat_id) if new_cat_id is not None else None,
            changed_by='user',
        ))

    await db.commit()
    cache.clear_for_user(current_user.id)

    final_id = correction.id if financial_changes else tx.id
    return TransactionPatchResult(
        id=final_id,
        re_categorized=re_categorized,
        reversal_id=reversal_id,
        correction_id=correction_id,
    )


@router.post("/reverse")
async def reverse_transactions(
    body: ReverseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reverse one or more committed transactions. Already-reversed rows are silently skipped."""
    reversed_ids: list[int] = []
    skipped_ids: list[int] = []

    for tx_id in body.ids:
        result = await db.execute(
            select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == current_user.id)
        )
        tx = result.scalar_one_or_none()
        if not tx or tx.reversed_by is not None or tx.reversal_of is not None:
            skipped_ids.append(tx_id)
            continue

        tx_direction = tx.direction.value if hasattr(tx.direction, 'value') else tx.direction
        tx_date = tx.date.replace(tzinfo=None) if tx.date and tx.date.tzinfo else tx.date
        reversal = Transaction(
            date=tx_date,
            amount=tx.amount,
            description=tx.description,
            direction='credit' if tx_direction == 'debit' else 'debit',
            category_id=tx.category_id,
            statement_id=tx.statement_id,
            currency=tx.currency,
            status='active',
            transaction_origin=tx.transaction_origin if isinstance(tx.transaction_origin, str) else tx.transaction_origin.value,
            reversal_of=tx.id,
            reversal_reason=body.reason,
            user_id=current_user.id,
        )
        db.add(reversal)
        await db.flush()
        tx.reversed_by = reversal.id
        reversed_ids.append(tx_id)

    await db.commit()
    cache.clear_for_user(current_user.id)
    return {"reversed": reversed_ids, "skipped": skipped_ids}


@router.get("/{id}/history", response_model=list[AuditLogOut])
async def get_transaction_history(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return audit log entries for a transaction, oldest first."""
    # Verify the transaction belongs to the current user before exposing its audit log.
    tx_result = await db.execute(
        select(Transaction.id).where(Transaction.id == id, Transaction.user_id == current_user.id)
    )
    if tx_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.transaction_id == id)
        .order_by(AuditLog.changed_at.asc())
    )
    return result.scalars().all()


@router.patch("/{id}/parent")
async def set_parent(
    id: int,
    body: ParentPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Link or unlink a transaction's parent (receipt decomposition)."""
    result = await db.execute(
        select(Transaction).where(Transaction.id == id, Transaction.user_id == current_user.id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    tx.parent_transaction_id = body.parent_transaction_id
    await db.commit()
    await db.refresh(tx)
    return tx

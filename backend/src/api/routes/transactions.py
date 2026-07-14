"""Transactions CRUD routes with filtering and pagination."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.schemas.transactions import TransactionCreate, TransactionOut, TransactionPatch
from src.db.session import get_db
from src.domain.models.category import Category
from src.domain.models.transaction import Transaction

router = APIRouter()


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    """Return (first_day, first_day_of_next_month) for a YYYY-MM string (tz-naive)."""
    year, mon = int(month[:4]), int(month[5:7])
    first_day = datetime(year, mon, 1)  # tz-naive to match TIMESTAMP WITHOUT TIME ZONE column
    # Advance to next month
    if mon == 12:
        next_year, next_mon = year + 1, 1
    else:
        next_year, next_mon = year, mon + 1
    first_day_next = datetime(next_year, next_mon, 1)
    return first_day, first_day_next


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    category_id: int | None = Query(default=None),
    direction: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List transactions with optional filters; ordered by date DESC."""
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.category))
        .order_by(Transaction.date.desc())
        .limit(limit)
        .offset(offset)
    )
    if month is not None:
        first_day, first_day_next = _month_bounds(month)
        stmt = stmt.where(Transaction.date >= first_day, Transaction.date < first_day_next)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if direction is not None:
        stmt = stmt.where(Transaction.direction == direction)

    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=TransactionOut, status_code=201)
async def create_transaction(body: TransactionCreate, db: AsyncSession = Depends(get_db)):
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
        statement_id=None,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(tx)

    # Reload with category eagerly
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.category))
        .where(Transaction.id == tx.id)
    )
    return result.scalar_one()


@router.patch("/{id}", response_model=TransactionOut)
async def patch_transaction(id: int, body: TransactionPatch, db: AsyncSession = Depends(get_db)):
    """Partial update — only fields provided (non-None) are changed."""
    result = await db.execute(
        select(Transaction).options(selectinload(Transaction.category)).where(Transaction.id == id)
    )
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    if body.category_id is not None:
        cat_result = await db.execute(select(Category).where(Category.id == body.category_id))
        if cat_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail=f"Category {body.category_id} not found.")
        tx.category_id = body.category_id

    if body.description is not None:
        tx.description = body.description

    await db.commit()
    await db.refresh(tx)

    # Reload to get fresh category relationship
    result = await db.execute(
        select(Transaction).options(selectinload(Transaction.category)).where(Transaction.id == id)
    )
    return result.scalar_one()


@router.delete("/{id}", status_code=204)
async def delete_transaction(id: int, db: AsyncSession = Depends(get_db)):
    """Delete a transaction. Returns 404 if not found."""
    result = await db.execute(select(Transaction).where(Transaction.id == id))
    tx = result.scalar_one_or_none()
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    await db.delete(tx)
    await db.commit()

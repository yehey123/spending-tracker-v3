"""Staged transaction review endpoints."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.domain.models.transaction import Transaction

router = APIRouter()


class StagedTransactionPatch(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    date: str | None = None
    description: str | None = Field(default=None, min_length=1, max_length=500)
    direction: str | None = None
    category_id: int | None = None
    currency: str | None = Field(default=None, max_length=3)


@router.patch("/{tx_id}")
async def patch_staged_transaction(
    tx_id: int,
    patch: StagedTransactionPatch,
    db: AsyncSession = Depends(get_db),
):
    """Direct update of a staged transaction — no reversal, no audit log."""
    tx = await db.get(Transaction, tx_id)
    if not tx or tx.status != 'staged':
        raise HTTPException(status_code=404, detail="Staged transaction not found")

    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(tx, field, value)
    await db.commit()
    await db.refresh(tx)
    return tx

"""Transaction flag review routes."""

from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.domain.models.transaction import Transaction
from src.domain.models.transaction_flag import TransactionFlag

router = APIRouter()


class FlagPatch(BaseModel):
    status: str  # "confirmed" or "rejected"
    category_id: int | None = None


# GET /flags/count MUST be registered BEFORE GET /{flag_id} to avoid routing conflict
@router.get("/count")
async def get_flag_count(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TransactionFlag).where(TransactionFlag.status == 'open')
    )
    return {"count": len(result.scalars().all())}


@router.get("")
async def list_flags(
    statement_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TransactionFlag).where(TransactionFlag.status == 'open')
    if statement_id is not None:
        # join to transaction to filter by statement
        stmt = stmt.join(Transaction, TransactionFlag.transaction_id == Transaction.id)
        stmt = stmt.where(Transaction.statement_id == statement_id)
    result = await db.execute(stmt)
    flags = result.scalars().all()
    return [
        {
            "id": f.id,
            "transaction_id": f.transaction_id,
            "flag_type": f.flag_type,
            "status": f.status,
            "flag_metadata": f.flag_metadata,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in flags
    ]


@router.patch("/{flag_id}")
async def resolve_flag(flag_id: int, body: FlagPatch, db: AsyncSession = Depends(get_db)):
    if body.status not in ("confirmed", "rejected"):
        raise HTTPException(status_code=422, detail="status must be 'confirmed' or 'rejected'")

    flag = await db.get(TransactionFlag, flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail="Flag not found.")
    if flag.status != 'open':
        raise HTTPException(status_code=409, detail="Flag is already resolved.")

    if body.status == "confirmed":
        tx = await db.get(Transaction, flag.transaction_id)
        if tx is not None:
            meta = flag.flag_metadata or {}
            cat_id = body.category_id if body.category_id is not None else meta.get("suggested_category_id")
            tx.category_id = cat_id

            merchant_key = meta.get("merchant_key")
            if merchant_key and cat_id is not None:
                from src.domain.services.categorizer import categorizer_service
                await categorizer_service.bulk_recategorize_by_merchant(merchant_key, cat_id, db)

    flag.status = body.status
    flag.resolved_by = 'user'
    flag.resolved_at = datetime.utcnow()
    await db.commit()
    return {"id": flag_id, "status": body.status}

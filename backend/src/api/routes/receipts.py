"""Receipts upload linking and listing routes."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.statements import ReceiptOut
from src.db.session import get_db
from src.domain.models.statement import Statement
from src.domain.models.transaction import Transaction

router = APIRouter()


class LinkBody(BaseModel):
    transaction_id: int


async def _find_suggested_parents(receipt: Statement, db: AsyncSession) -> list[int]:
    if receipt.declared_total is None or receipt.uploaded_at is None:
        return []
    uploaded_naive = receipt.uploaded_at.replace(tzinfo=None)
    window_start = uploaded_naive - timedelta(days=5)
    window_end = uploaded_naive + timedelta(days=5)
    amount = Decimal(str(receipt.declared_total))
    lower = amount * Decimal('0.95')
    upper = amount * Decimal('1.05')
    result = await db.execute(
        select(Transaction.id)
        .where(
            Transaction.status == 'active',
            Transaction.reversed_by.is_(None),
            Transaction.parent_transaction_id.is_(None),
            Transaction.amount.between(lower, upper),
            Transaction.date >= window_start,
            Transaction.date <= window_end,
        )
        .limit(10)
    )
    return [row[0] for row in result.all()]


@router.get("", response_model=list[ReceiptOut])
async def list_receipts(
    offset: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[ReceiptOut]:
    result = await db.execute(
        select(Statement)
        .where(Statement.file_type == 'receipt')
        .order_by(Statement.uploaded_at.desc())
        .offset(offset)
        .limit(limit)
    )
    receipts = result.scalars().all()
    out = []
    for r in receipts:
        suggested = await _find_suggested_parents(r, db)
        out.append(ReceiptOut(
            id=r.id,
            filename=r.filename,
            status=str(r.status.value) if hasattr(r.status, 'value') else str(r.status),
            uploaded_at=r.uploaded_at,
            declared_total=r.declared_total,
            suggested_parent_ids=suggested,
        ))
    return out


@router.post("/{receipt_id}/link")
async def link_receipt(
    receipt_id: int,
    body: LinkBody,
    db: AsyncSession = Depends(get_db),
):
    receipt = await db.get(Statement, receipt_id)
    if receipt is None or receipt.file_type != 'receipt':
        raise HTTPException(status_code=404, detail="Receipt not found.")

    target_tx = await db.get(Transaction, body.transaction_id)
    if target_tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    result = await db.execute(
        select(Transaction).where(Transaction.statement_id == receipt_id)
    )
    receipt_txs = result.scalars().all()

    if receipt.declared_total is not None:
        receipt_amount = Decimal(str(receipt.declared_total))
    elif receipt_txs:
        receipt_amount = sum(tx.amount for tx in receipt_txs)
    else:
        receipt_amount = None

    if receipt_amount is not None:
        tx_amount = Decimal(str(target_tx.amount))
        denom = max(receipt_amount, tx_amount)
        if denom > 0 and abs(receipt_amount - tx_amount) / denom > Decimal('0.05'):
            raise HTTPException(status_code=422, detail="AMOUNT_MISMATCH")

    for tx in receipt_txs:
        tx.parent_transaction_id = body.transaction_id
    await db.commit()
    return {"linked": receipt_id, "transaction_id": body.transaction_id}


@router.post("/{receipt_id}/unlink")
async def unlink_receipt(receipt_id: int, db: AsyncSession = Depends(get_db)):
    receipt = await db.get(Statement, receipt_id)
    if receipt is None or receipt.file_type != 'receipt':
        raise HTTPException(status_code=404, detail="Receipt not found.")

    result = await db.execute(
        select(Transaction).where(Transaction.statement_id == receipt_id)
    )
    for tx in result.scalars().all():
        tx.parent_transaction_id = None
    await db.commit()
    return {"unlinked": receipt_id}


@router.post("/{receipt_id}/reassign")
async def reassign_receipt(
    receipt_id: int,
    body: LinkBody,
    db: AsyncSession = Depends(get_db),
):
    await unlink_receipt(receipt_id, db)
    return await link_receipt(receipt_id, body, db)

"""Detect suspected transfers between accounts (same amount, opposite direction, ±3 days)."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.transaction import Transaction
from src.domain.models.transaction_flag import TransactionFlag


async def detect_transfers(account_id: int | None, db: AsyncSession) -> int:
    """
    Scan transactions for cross-account debit↔credit pairs within ±3 days of same amount.
    If account_id is None, scans all accounts. Returns count of pairs flagged.
    """
    base_where = [
        Transaction.status == 'active',
        Transaction.transfer_status.is_(None),
        Transaction.deleted_at.is_(None),
        Transaction.account_id.is_not(None),
    ]
    if account_id is not None:
        base_where.append(Transaction.account_id == account_id)

    source_txns_result = await db.execute(
        select(Transaction).where(*base_where)
    )
    source_txns = source_txns_result.scalars().all()

    pairs = 0
    seen_pairs: set[tuple[int, int]] = set()

    for tx in source_txns:
        # Direction.DEBIT == 'debit' (str enum subclass) — safe string comparison
        opposite = 'credit' if tx.direction == 'debit' else 'debit'
        # Strip tzinfo: Transaction.date is TIMESTAMP WITHOUT TIME ZONE
        tx_date = tx.date.replace(tzinfo=None) if tx.date.tzinfo else tx.date
        window_low = tx_date - timedelta(days=3)
        window_high = tx_date + timedelta(days=3)

        peers_result = await db.execute(
            select(Transaction).where(
                Transaction.account_id != tx.account_id,
                Transaction.account_id.is_not(None),
                Transaction.amount == tx.amount,
                Transaction.direction == opposite,
                Transaction.status == 'active',
                Transaction.transfer_status.is_(None),
                Transaction.deleted_at.is_(None),
                Transaction.date >= window_low,
                Transaction.date <= window_high,
            )
        )
        peers = peers_result.scalars().all()

        for peer in peers:
            pair_key = (min(tx.id, peer.id), max(tx.id, peer.id))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            tx.transfer_status = 'suspected'
            tx.transfer_peer_id = peer.id
            peer.transfer_status = 'suspected'
            peer.transfer_peer_id = tx.id

            days_apart = abs((tx.date - peer.date).days)
            db.add(TransactionFlag(
                transaction_id=tx.id,
                flag_type='suspected_transfer',
                status='open',
                flag_metadata={
                    "peer_id": peer.id,
                    "peer_account_id": peer.account_id,
                    "days_apart": days_apart,
                    "amount": str(tx.amount),
                },
            ))
            pairs += 1

    await db.flush()
    return pairs

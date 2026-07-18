"""Nightly TTL cleanup — expires staged statements older than 7 days."""

from datetime import datetime, timezone, timedelta
from sqlalchemy import update, delete, select
from src.db.session import AsyncSessionLocal
from src.domain.models.statement import Statement
from src.domain.models.transaction import Transaction

STAGED_TTL_DAYS = 7


async def run_ttl_cleanup():
    cutoff = datetime.now(timezone.utc) - timedelta(days=STAGED_TTL_DAYS)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Statement.id)
            .where(Statement.status == 'staged')
            .where(Statement.uploaded_at < cutoff)
        )
        expired_ids = [row[0] for row in result]

        for stmt_id in expired_ids:
            # Hard-delete staged transactions (pre-ledger, safe to delete)
            await db.execute(
                delete(Transaction)
                .where(Transaction.statement_id == stmt_id, Transaction.status == 'staged')
            )
            # Mark statement as discarded
            await db.execute(
                update(Statement)
                .where(Statement.id == stmt_id)
                .values(status='discarded')
            )

        await db.commit()

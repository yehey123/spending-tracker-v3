"""Nightly TTL cleanup — expires staged statements, purges expired tokens."""

from datetime import datetime, timezone, timedelta
from sqlalchemy import update, delete, select
from src.db.session import get_admin_db
from src.domain.models.statement import Statement
from src.domain.models.transaction import Transaction
from src.domain.models.user import RefreshToken
from src.domain.models.invite_token import InviteToken

STAGED_TTL_DAYS = 7


async def run_ttl_cleanup():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=STAGED_TTL_DAYS)
    async with get_admin_db() as db:
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

        await db.execute(
            delete(RefreshToken).where(RefreshToken.absolute_expires_at < now)
        )

        await db.execute(
            delete(InviteToken).where(InviteToken.expires_at < now)
        )

        await db.commit()

"""Monthly credit rollover — grants credits to all users on the 1st of each month.

Idempotent: credit_rollovers PRIMARY KEY (user_id, period) prevents double-grant.
"""
from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)


async def run_monthly_rollover() -> None:
    from sqlalchemy import select
    from src.db.session import AsyncSessionLocal
    from src.domain.models.user import User
    from src.domain.services.credits import grant_monthly

    period = date.today().replace(day=1)

    async with AsyncSessionLocal() as db:
        user_ids = (await db.execute(select(User.id))).scalars().all()
        granted = 0
        skipped = 0
        for uid in user_ids:
            result = await grant_monthly(user_id=uid, period=period, db=db)
            if result:
                granted += 1
            else:
                skipped += 1

        await db.commit()
        logger.info(
            "Monthly rollover complete: granted=%d, skipped=%d, period=%s",
            granted, skipped, period,
        )

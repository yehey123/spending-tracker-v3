"""Admin bootstrap — runs once at startup to ensure at least one admin exists."""

from __future__ import annotations

import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.user import SystemConfig, User

logger = logging.getLogger(__name__)

BOOTSTRAP_KEY = "admin_bootstrapped"


async def run_admin_bootstrap(db: AsyncSession) -> None:
    """Promote a user to admin if no admin exists yet.

    Priority order:
      1. ADMIN_SEED_EMAIL env var → promote that user if they exist.
      2. First registered user (lowest created_at) → promote as fallback.
      3. If no users exist, skip silently.
    Writes system_config key 'admin_bootstrapped' = 'true' after success to
    prevent re-running on every restart.
    """
    already = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == BOOTSTRAP_KEY)
    )).scalar_one_or_none()
    if already and already.value == "true":
        return

    seed_email = os.getenv("ADMIN_SEED_EMAIL")
    target: User | None = None

    if seed_email:
        target = (await db.execute(
            select(User).where(User.email == seed_email)
        )).scalar_one_or_none()
        if not target:
            logger.warning("ADMIN_SEED_EMAIL=%s not found — falling back to first user", seed_email)

    if target is None:
        target = (await db.execute(
            select(User).order_by(User.created_at.asc()).limit(1)
        )).scalar_one_or_none()

    if target is None:
        logger.info("Bootstrap: no users yet — skipping. Will retry on next restart.")
        return

    if not target.is_admin:
        target.is_admin = True
        logger.info("Bootstrap: promoted %s to admin.", target.email)

    db.add(SystemConfig(key=BOOTSTRAP_KEY, value="true"))
    await db.commit()

"""Credit quota tests (E14).

Service-level tests call grant_monthly and atomic_debit directly via db_session
to avoid depending on the OCR pipeline. Route-level tests use the standard
client fixture (get_current_user override active).

run_monthly_rollover opens AsyncSessionLocal (the production DB factory) and
is NOT tested here — only the underlying grant_monthly service is tested.
"""

from datetime import date, datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import select

from src.domain.models.credit_ledger import CreditLedger
from src.domain.models.credit_rollover import CreditRollover
from src.domain.services.credits import (
    InsufficientCredits,
    atomic_debit,
    get_balance,
    grant_monthly,
)


# ---------------------------------------------------------------------------
# Service-level: grant_monthly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grant_monthly_credits_user(test_user, db_session):
    """grant_monthly deposits default 30 credits and returns True."""
    period = date(2026, 1, 1)
    granted = await grant_monthly(test_user.id, period, db_session)
    assert granted is True

    balance = await get_balance(test_user.id, db_session)
    assert balance == 30


@pytest.mark.asyncio
async def test_grant_monthly_idempotent(test_user, db_session):
    """Calling grant_monthly twice for the same period grants credits only once."""
    period = date(2026, 2, 1)
    first = await grant_monthly(test_user.id, period, db_session)
    # Commit so the idempotency-branch rollback only affects the current (empty) tx,
    # not the already-granted data.
    await db_session.commit()
    second = await grant_monthly(test_user.id, period, db_session)

    assert first is True
    assert second is False

    balance = await get_balance(test_user.id, db_session)
    assert balance == 30, "credits must not be doubled on idempotent call"


@pytest.mark.asyncio
async def test_grant_monthly_different_periods(test_user, db_session):
    """Each distinct period grants credits independently."""
    await grant_monthly(test_user.id, date(2026, 3, 1), db_session)
    await grant_monthly(test_user.id, date(2026, 4, 1), db_session)

    balance = await get_balance(test_user.id, db_session)
    assert balance == 60


# ---------------------------------------------------------------------------
# Service-level: atomic_debit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_atomic_debit_reduces_balance(test_user, db_session):
    """atomic_debit deducts the provider's cost and returns credits debited."""
    await grant_monthly(test_user.id, date(2026, 5, 1), db_session)
    stmt_id = str(uuid.uuid4())

    debited = await atomic_debit(test_user.id, "anthropic", stmt_id, db_session)
    assert debited == 3  # default anthropic weight

    balance = await get_balance(test_user.id, db_session)
    assert balance == 27


@pytest.mark.asyncio
async def test_atomic_debit_raises_insufficient_credits(test_user, db_session):
    """atomic_debit raises InsufficientCredits when balance < cost."""
    # No credits granted — balance is 0
    with pytest.raises(InsufficientCredits) as exc_info:
        await atomic_debit(test_user.id, "anthropic", str(uuid.uuid4()), db_session)

    err = exc_info.value
    assert err.balance == 0
    assert err.cost == 3


@pytest.mark.asyncio
async def test_atomic_debit_tesseract_free(test_user, db_session):
    """Tesseract (cost=0) is free — no balance needed, returns 0."""
    debited = await atomic_debit(test_user.id, "tesseract", str(uuid.uuid4()), db_session)
    assert debited == 0
    assert await get_balance(test_user.id, db_session) == 0


@pytest.mark.asyncio
async def test_atomic_debit_idempotent(test_user, db_session):
    """Duplicate debit key is silently skipped (idempotency_key unique constraint)."""
    await grant_monthly(test_user.id, date(2026, 6, 1), db_session)
    await db_session.commit()  # persist grant before first debit

    stmt_id = "stmt-idempotent-123"
    first = await atomic_debit(test_user.id, "anthropic", stmt_id, db_session)
    await db_session.commit()  # persist debit before duplicate attempt

    second = await atomic_debit(test_user.id, "anthropic", stmt_id, db_session)

    assert first == 3
    assert second == 0  # duplicate silently skipped
    assert await get_balance(test_user.id, db_session) == 27


# ---------------------------------------------------------------------------
# Route-level: GET /credits/balance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_credits_balance_zero_for_new_user(client):
    """GET /credits/balance returns 0 balance for a user with no credits."""
    res = await client.get("/credits/balance")
    assert res.status_code == 200
    body = res.json()
    assert body["balance"] == 0
    assert body["monthly_grant"] == 30
    assert "weights" in body
    assert "anthropic" in body["weights"]


@pytest.mark.asyncio
async def test_credits_balance_reflects_grants(test_user, client, db_session):
    """GET /credits/balance reflects credits granted via the service."""
    await grant_monthly(test_user.id, date(2026, 7, 1), db_session)
    # Route handler opens a separate READ COMMITTED session; must commit first
    # so the new session sees the granted credits.
    await db_session.commit()

    res = await client.get("/credits/balance")
    assert res.status_code == 200
    assert res.json()["balance"] == 30

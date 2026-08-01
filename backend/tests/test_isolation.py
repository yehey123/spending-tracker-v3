"""Cross-tenant data isolation tests (E13).

Each test creates resources as user A (test_user) and attempts to access or
mutate them as user B. Expected result is always 404 — the row must be
invisible to user B, not merely forbidden.
"""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text

import tests.conftest as _conftest
from src.main import app
from src.core.auth import create_access_token, hash_password
from src.core.deps import get_current_user
from src.db.session import get_db
from src.domain.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user_b(email: str) -> User:
    """Insert a second user into the test DB using the shared admin session."""
    uid = uuid.uuid4()
    async with _conftest._TestingSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.is_admin', 'true', false)"))
        await db.execute(
            text(
                "INSERT INTO users (id, email, password_hash) "
                "VALUES (:id, :email, :pw) ON CONFLICT DO NOTHING"
            ),
            {"id": str(uid), "email": email, "pw": hash_password("TestPass1!")},
        )
        await db.commit()
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one()


@asynccontextmanager
async def _as_user(user_b: User):
    """Context manager that temporarily swaps get_current_user to return user_b."""
    original = app.dependency_overrides.get(get_current_user)

    async def _override():
        return user_b

    app.dependency_overrides[get_current_user] = _override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        if original is not None:
            app.dependency_overrides[get_current_user] = original
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_b_cannot_patch_user_a_transaction(test_user: User):
    """PATCH /transactions/{id} must return 404 when the tx belongs to a different user."""
    from src.domain.models.transaction import Transaction

    async with _conftest._TestingSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.is_admin', 'true', false)"))
        tx = Transaction(
            date=datetime(2026, 1, 1),
            amount=100,
            description="User A private tx",
            direction="debit",
            status="active",
            transaction_origin="manual",
            user_id=test_user.id,
        )
        db.add(tx)
        await db.commit()
        await db.refresh(tx)
        tx_id = tx.id

    user_b = await _create_user_b("iso_patch_b@test.com")
    async with _as_user(user_b) as client:
        res = await client.patch(f"/transactions/{tx_id}", json={"description": "hacked"})
        assert res.status_code == 404, f"Expected 404, got {res.status_code}: {res.text}"


@pytest.mark.asyncio
async def test_user_b_reverse_skips_user_a_transaction(test_user: User):
    """POST /transactions/reverse must silently skip transactions belonging to other users."""
    from src.domain.models.transaction import Transaction

    async with _conftest._TestingSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.is_admin', 'true', false)"))
        tx = Transaction(
            date=datetime(2026, 1, 1),
            amount=50,
            description="Tx to not reverse",
            direction="credit",
            status="active",
            transaction_origin="manual",
            user_id=test_user.id,
        )
        db.add(tx)
        await db.commit()
        await db.refresh(tx)
        tx_id = tx.id

    user_b = await _create_user_b("iso_reverse_b@test.com")
    async with _as_user(user_b) as client:
        res = await client.post("/transactions/reverse", json={"ids": [tx_id], "reason": "other"})
        assert res.status_code == 200
        body = res.json()
        assert tx_id in body["skipped"], "tx should be skipped, not reversed"
        assert tx_id not in body["reversed"]


@pytest.mark.asyncio
async def test_user_b_cannot_commit_user_a_statement(test_user: User):
    """POST /statements/{id}/commit must return 404 for a statement belonging to another user."""
    from src.domain.models.statement import Statement

    async with _conftest._TestingSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.is_admin', 'true', false)"))
        stmt = Statement(
            filename="userA.png",
            type="image",
            status="staged",
            ocr_provider="tesseract",
            user_id=test_user.id,
        )
        db.add(stmt)
        await db.commit()
        await db.refresh(stmt)
        stmt_id = stmt.id

    user_b = await _create_user_b("iso_commit_b@test.com")
    async with _as_user(user_b) as client:
        res = await client.post(f"/statements/{stmt_id}/commit")
        assert res.status_code == 404, (
            f"Expected 404 (statement must not be visible to user B), "
            f"got {res.status_code}: {res.text}"
        )


@pytest.mark.asyncio
async def test_list_transactions_excludes_other_users(test_user: User):
    """GET /transactions must return only the authenticated user's rows."""
    from src.domain.models.transaction import Transaction

    user_b = await _create_user_b("iso_list_b@test.com")

    async with _conftest._TestingSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.is_admin', 'true', false)"))
        for owner, desc in [(test_user, "A's tx"), (user_b, "B's tx")]:
            db.add(Transaction(
                date=datetime(2026, 1, 1),
                amount=10,
                description=desc,
                direction="debit",
                status="active",
                transaction_origin="manual",
                user_id=owner.id,
            ))
        await db.commit()

    async with _as_user(user_b) as client:
        res = await client.get("/transactions")
        assert res.status_code == 200
        descriptions = [t["description"] for t in res.json()]
        assert "B's tx" in descriptions
        assert "A's tx" not in descriptions, "User A's transaction must not appear for user B"

"""Admin route tests (E13/E17).

The conftest override makes get_current_user return test_user (is_admin=True),
so admin routes work by default. Non-admin scenarios use _as_non_admin() to
swap the override to a regular user.

The deactivated→403 test pops the override entirely and drives a real JWT
through UserContextMiddleware, which is the only way to exercise the
is_active check inside the real get_current_user dependency.
"""

import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from unittest.mock import AsyncMock, patch

import tests.conftest as _conftest
from src.core.auth import create_access_token, hash_password
from src.core.bootstrap import BOOTSTRAP_KEY
from src.core.deps import get_current_user
from src.domain.models.user import SystemConfig, User
from src.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user(email: str, *, is_admin: bool = False) -> User:
    """Insert a user into the test DB with admin RLS bypass."""
    uid = uuid.uuid4()
    async with _conftest._TestingSessionLocal() as db:
        await db.execute(text("SELECT set_config('app.is_admin', 'true', false)"))
        await db.execute(
            text(
                "INSERT INTO users (id, email, password_hash, is_admin) "
                "VALUES (:id, :email, :pw, :admin) ON CONFLICT DO NOTHING"
            ),
            {
                "id": str(uid),
                "email": email,
                "pw": hash_password("TestPass1!"),
                "admin": is_admin,
            },
        )
        await db.commit()
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one()


@asynccontextmanager
async def _as_non_admin(user: User):
    """Temporarily override get_current_user to return a non-admin user."""
    original = app.dependency_overrides.get(get_current_user)

    async def _override():
        return user

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
# List users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_list_users(client, test_user):
    """GET /admin/users returns the user list for an admin."""
    res = await client.get("/admin/users")
    assert res.status_code == 200
    body = res.json()
    assert "users" in body
    assert "total" in body
    emails = [u["email"] for u in body["users"]]
    assert test_user.email in emails


@pytest.mark.asyncio
async def test_non_admin_list_users_forbidden():
    """GET /admin/users returns 403 for a non-admin caller."""
    non_admin = await _create_user("nonadmin_list@test.com")
    async with _as_non_admin(non_admin) as c:
        res = await c.get("/admin/users")
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Deactivate / reactivate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_deactivate_user(client, db_session):
    """POST /admin/users/{id}/deactivate sets is_active=False and revokes sessions."""
    from src.domain.models.user import RefreshToken
    from src.core.auth import generate_refresh_token
    from datetime import datetime, timedelta, timezone

    target = await _create_user("deactivate_target@test.com")

    # Give target user an active refresh token
    opaque, token_hash = generate_refresh_token()
    now = datetime.now(tz=timezone.utc)
    db_session.add(RefreshToken(
        token_hash=token_hash,
        user_id=target.id,
        expires_at=now + timedelta(days=7),
        absolute_expires_at=now + timedelta(days=30),
        session_id=uuid.uuid4(),
    ))
    await db_session.commit()

    res = await client.post(f"/admin/users/{target.id}/deactivate")
    assert res.status_code == 200
    body = res.json()
    assert body["is_active"] is False

    # All refresh tokens for target must be deleted
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.user_id == target.id)
    )
    assert result.scalars().all() == [], "deactivated user's refresh tokens must be purged"


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_self(client, test_user):
    """POST /admin/users/{own_id}/deactivate returns 400."""
    res = await client.post(f"/admin/users/{test_user.id}/deactivate")
    assert res.status_code == 400
    assert "own account" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_reactivate_user(client):
    """POST /admin/users/{id}/reactivate sets is_active=True."""
    target = await _create_user("reactivate_target@test.com")

    # Deactivate first
    await client.post(f"/admin/users/{target.id}/deactivate")

    res = await client.post(f"/admin/users/{target.id}/reactivate")
    assert res.status_code == 200
    assert res.json()["is_active"] is True


@pytest.mark.asyncio
async def test_deactivated_user_gets_403(test_user, test_user_token, db_session):
    """A deactivated account returns 403, not 401, on protected routes.

    This test pops the get_current_user override so the real dependency runs,
    which is the only path that checks is_active. A real JWT is sent via the
    Authorization header so UserContextMiddleware sets request.state.user_id.
    """
    original_override = app.dependency_overrides.get(get_current_user)

    await db_session.execute(
        text("UPDATE users SET is_active = false WHERE id = :uid"),
        {"uid": str(test_user.id)},
    )
    await db_session.commit()
    app.dependency_overrides.pop(get_current_user, None)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get(
                "/categories",
                headers={"Authorization": f"Bearer {test_user_token}"},
            )
        assert res.status_code == 403
        assert "deactivated" in res.json()["detail"].lower()
    finally:
        await db_session.execute(
            text("UPDATE users SET is_active = true WHERE id = :uid"),
            {"uid": str(test_user.id)},
        )
        await db_session.commit()
        if original_override is not None:
            app.dependency_overrides[get_current_user] = original_override
        else:
            app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Resend invite
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_resend_invite(client):
    """POST /admin/resend-invite/{id} issues a new invite token (email mocked)."""
    target = await _create_user("resend_target@test.com")

    # Deactivate so resend-invite is valid
    await client.post(f"/admin/users/{target.id}/deactivate")

    with patch(
        "src.api.routes.admin.send_user_invite_email",
        new_callable=AsyncMock,
    ) as mock_send:
        res = await client.post(f"/admin/resend-invite/{target.id}")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "sent"
    assert body["email"] == target.email
    mock_send.assert_awaited_once()


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bootstrap_already_bootstrapped_409(client, db_session):
    """POST /admin/bootstrap returns 409 when the system_config key already exists."""
    db_session.add(SystemConfig(key=BOOTSTRAP_KEY, value="true"))
    await db_session.commit()

    res = await client.post("/admin/bootstrap")
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_bootstrap_promotes_first_user(test_user, db_session):
    """POST /admin/bootstrap promotes the first user when no SystemConfig key exists."""
    await db_session.execute(text("DELETE FROM system_config"))
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/admin/bootstrap")

    assert res.status_code == 200
    body = res.json()
    assert body["email"] == test_user.email

"""Refresh token rotation and security tests (E12/E15).

Tests insert RefreshToken rows directly via db_session to avoid going through
register/login, then call /auth/token/refresh with the opaque token cookie.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from src.core.auth import generate_refresh_token, hash_refresh_token
from src.domain.models.user import RefreshToken
from src.main import app


async def _insert_rt(
    db_session,
    user_id: uuid.UUID,
    *,
    rotated: bool = False,
    window_expired: bool = False,
    abs_expired: bool = False,
) -> tuple[str, uuid.UUID]:
    """Insert a RefreshToken row; return (opaque_token, session_id)."""
    opaque, token_hash = generate_refresh_token()
    now = datetime.now(tz=timezone.utc)
    session_id = uuid.uuid4()
    rt = RefreshToken(
        token_hash=token_hash,
        user_id=user_id,
        expires_at=(now - timedelta(hours=1)) if window_expired else (now + timedelta(days=7)),
        absolute_expires_at=(now - timedelta(hours=1)) if abs_expired else (now + timedelta(days=30)),
        session_id=session_id,
        device_name="test-device",
        rotated_at=now if rotated else None,
    )
    db_session.add(rt)
    await db_session.commit()
    return opaque, session_id


@pytest.mark.asyncio
async def test_refresh_rotation_happy_path(test_user, db_session):
    """Valid refresh token issues new access token and marks old one rotated."""
    opaque, _ = await _insert_rt(db_session, test_user.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/auth/token/refresh", cookies={"refresh_token": opaque})

    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"

    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(opaque))
    )
    old_rt = result.scalar_one_or_none()
    assert old_rt is not None
    assert old_rt.rotated_at is not None, "old token must be marked rotated"


@pytest.mark.asyncio
async def test_refresh_replay_attack_rejected(test_user, db_session):
    """Re-using an already-rotated opaque token returns 401."""
    opaque, _ = await _insert_rt(db_session, test_user.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        first = await c.post("/auth/token/refresh", cookies={"refresh_token": opaque})
    assert first.status_code == 200, "first refresh should succeed"

    # Fresh client with ONLY the original opaque — avoids httpx cookie-jar ambiguity
    # where the rotated new token from the first response could shadow the original.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c2:
        second = await c2.post("/auth/token/refresh", cookies={"refresh_token": opaque})

    assert second.status_code == 401
    assert "already used" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_pre_rotated_rejected(test_user, db_session):
    """A token that was rotated before the request (e.g. by another process) is rejected."""
    opaque, _ = await _insert_rt(db_session, test_user.id, rotated=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/auth/token/refresh", cookies={"refresh_token": opaque})

    assert res.status_code == 401
    assert "already used" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_window_expired_rejected(test_user, db_session):
    """A token past its 7-day rolling window is rejected with 401."""
    opaque, _ = await _insert_rt(db_session, test_user.id, window_expired=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/auth/token/refresh", cookies={"refresh_token": opaque})

    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_absolute_cap_enforced(test_user, db_session):
    """A token past the 30-day absolute cap is rejected and the DB row deleted."""
    opaque, _ = await _insert_rt(db_session, test_user.id, abs_expired=True)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post("/auth/token/refresh", cookies={"refresh_token": opaque})

    assert res.status_code == 401

    # The route deletes the row on absolute-cap expiry
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(opaque))
    )
    assert result.scalar_one_or_none() is None, "expired row must be deleted from DB"


@pytest.mark.asyncio
async def test_refresh_missing_cookie_returns_401(client):
    """POST /auth/token/refresh with no refresh_token cookie returns 401."""
    res = await client.post("/auth/token/refresh")
    assert res.status_code == 401
    assert "missing" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_unknown_token_returns_401(client):
    """A well-formed but unknown opaque token returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post(
            "/auth/token/refresh",
            cookies={"refresh_token": "totally-unknown-opaque-value"},
        )
    assert res.status_code == 401

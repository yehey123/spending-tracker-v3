"""Session management tests — GET /auth/sessions, DELETE /auth/sessions/{id}, POST /auth/logout.

These routes use require_user (src.core.auth), NOT get_current_user (src.core.deps).
require_user is NOT overridden in conftest, so tests must send a real JWT via
the Authorization: Bearer header. The get_db override is still active, so
the route handler operates against the test DB.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from src.core.auth import create_access_token, generate_refresh_token, hash_refresh_token
from src.domain.models.user import RefreshToken
from src.main import app


async def _insert_rt(
    db_session,
    user_id: uuid.UUID,
    session_id: uuid.UUID | None = None,
) -> tuple[str, uuid.UUID]:
    """Insert an active RefreshToken. Returns (opaque, session_id)."""
    opaque, token_hash = generate_refresh_token()
    now = datetime.now(tz=timezone.utc)
    sid = session_id or uuid.uuid4()
    db_session.add(RefreshToken(
        token_hash=token_hash,
        user_id=user_id,
        expires_at=now + timedelta(days=7),
        absolute_expires_at=now + timedelta(days=30),
        session_id=sid,
        device_name="test-device",
    ))
    await db_session.commit()
    return opaque, sid


@pytest.mark.asyncio
async def test_list_sessions_returns_active_sessions(test_user, test_user_token, db_session):
    """GET /auth/sessions lists active RefreshToken sessions for the caller."""
    _, sid = await _insert_rt(db_session, test_user.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get(
            "/auth/sessions",
            headers={"Authorization": f"Bearer {test_user_token}"},
        )

    assert res.status_code == 200
    sessions = res.json()
    assert isinstance(sessions, list)
    session_ids = [s["session_id"] for s in sessions]
    assert str(sid) in session_ids


@pytest.mark.asyncio
async def test_list_sessions_is_current_flag(test_user, db_session):
    """The session matching the JWT sid claim is marked is_current=True."""
    session_id = uuid.uuid4()
    await _insert_rt(db_session, test_user.id, session_id=session_id)

    # Create a token that embeds this session_id in the sid claim
    token_with_sid = create_access_token(test_user.id, is_admin=True, session_id=session_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get(
            "/auth/sessions",
            headers={"Authorization": f"Bearer {token_with_sid}"},
        )

    assert res.status_code == 200
    sessions = res.json()
    matching = [s for s in sessions if s["session_id"] == str(session_id)]
    assert matching, "the inserted session must appear in the list"
    assert matching[0]["is_current"] is True


@pytest.mark.asyncio
async def test_revoke_session_deletes_tokens(test_user, test_user_token, db_session):
    """DELETE /auth/sessions/{session_id} removes all RefreshTokens for that session."""
    _, sid = await _insert_rt(db_session, test_user.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.delete(
            f"/auth/sessions/{sid}",
            headers={"Authorization": f"Bearer {test_user_token}"},
        )

    assert res.status_code == 204

    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.session_id == sid)
    )
    assert result.scalars().all() == [], "revoked session tokens must be deleted"


@pytest.mark.asyncio
async def test_revoke_nonexistent_session_returns_404(test_user, test_user_token):
    """DELETE /auth/sessions/{unknown} returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.delete(
            f"/auth/sessions/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {test_user_token}"},
        )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_logout_marks_refresh_token_rotated(test_user, test_user_token, db_session):
    """POST /auth/logout marks the submitted refresh token as rotated and clears cookies."""
    opaque, _ = await _insert_rt(db_session, test_user.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {test_user_token}"},
            cookies={"refresh_token": opaque},
        )

    assert res.status_code == 204

    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(opaque))
    )
    rt = result.scalar_one_or_none()
    assert rt is not None
    assert rt.rotated_at is not None, "logout must mark refresh token as rotated"


@pytest.mark.asyncio
async def test_logout_without_refresh_cookie_still_succeeds(test_user, test_user_token):
    """POST /auth/logout returns 204 even if no refresh_token cookie is sent."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {test_user_token}"},
        )
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_sessions_require_auth():
    """GET /auth/sessions without Authorization returns 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/auth/sessions")
    assert res.status_code == 401

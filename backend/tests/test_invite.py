"""Invite gate tests (E11).

All email sends are already wrapped in try/except inside request_access and
admin_approve, so SMTP failures are swallowed. admin_deny has no email.
The resend_invite in admin.py is tested separately in test_admin.py.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from unittest.mock import AsyncMock, patch

from datetime import datetime, timedelta, timezone

from src.core.config import settings
from src.core.email import invite_expires_at, make_admin_link_sig, make_hmac_sig, verify_hmac_sig
from src.domain.models.access_request import AccessRequest
from src.domain.models.invite_token import InviteToken
from src.main import app


def _link(action, req_id, ttl=timedelta(hours=1)):
    exp = int((datetime.now(timezone.utc) + ttl).timestamp())
    return {"exp": exp, "sig": make_admin_link_sig(action, req_id, exp)}


def test_invite_expires_in_24_hours():
    """RULE-SEC-07: invite tokens live 24h, matching admin resend-invite (INVITE_TOKEN_EXPIRE_HOURS)."""
    remaining = invite_expires_at() - datetime.now(timezone.utc)
    assert timedelta(hours=23, minutes=59) < remaining <= timedelta(hours=24)


# ---------------------------------------------------------------------------
# POST /request-access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_request_access_creates_pending_row(client, db_session):
    """POST /request-access persists an AccessRequest with status='pending'."""
    res = await client.post(
        "/request-access",
        json={"email": "applicant@example.com", "reason": "I need access"},
    )
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "pending"
    assert body["email"] == "applicant@example.com"

    result = await db_session.execute(
        select(AccessRequest).where(AccessRequest.email == "applicant@example.com")
    )
    row = result.scalar_one_or_none()
    assert row is not None
    assert row.status == "pending"


@pytest.mark.asyncio
async def test_request_access_email_failure_returns_502(client, db_session):
    """POST /request-access returns 502 when operator email fails, and does not persist the row."""
    with patch(
        "src.api.routes.invite.send_operator_request_email",
        side_effect=Exception("SMTP down"),
    ):
        res = await client.post(
            "/request-access",
            json={"email": "failmail@example.com"},
        )
    assert res.status_code == 502
    assert "email" in res.json()["detail"].lower()

    result = await db_session.execute(
        select(AccessRequest).where(AccessRequest.email == "failmail@example.com")
    )
    assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# GET /admin/approve/{request_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_hmac_rejected_on_approve(client, db_session):
    """GET /admin/approve/{id} with a bad sig returns 403."""
    req = AccessRequest(email="sig_test@example.com", status="pending")
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get(f"/admin/approve/{req.id}", params={"exp": 9999999999, "sig": "badsig"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_invalid_hmac_rejected_on_deny(client, db_session):
    """GET /admin/deny/{id} with a bad sig returns 403."""
    req = AccessRequest(email="deny_sig@example.com", status="pending")
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get(f"/admin/deny/{req.id}", params={"exp": 9999999999, "sig": "badsig"})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_approve_creates_invite_token(db_session):
    """GET /admin/approve/{id} with valid sig creates an InviteToken row."""
    req = AccessRequest(email="approve_me@example.com", status="pending")
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    params = _link("approve", req.id)

    with patch("src.api.routes.invite.send_user_invite_email", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get(f"/admin/approve/{req.id}", params=params)

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "approved"

    # InviteToken row must exist for this email
    result = await db_session.execute(
        select(InviteToken).where(InviteToken.email == "approve_me@example.com")
    )
    token_row = result.scalar_one_or_none()
    assert token_row is not None
    assert token_row.consumed_at is None

    # AccessRequest status must be updated
    await db_session.refresh(req)
    assert req.status == "approved"


@pytest.mark.asyncio
async def test_approve_email_failure_does_not_persist_token(db_session):
    """If invite email fails, no InviteToken row is saved but request is still approved."""
    req = AccessRequest(email="emailfail@example.com", status="pending")
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    params = _link("approve", req.id)

    with patch(
        "src.api.routes.invite.send_user_invite_email",
        new_callable=AsyncMock,
        side_effect=Exception("SMTP down"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get(f"/admin/approve/{req.id}", params=params)

    assert res.status_code == 502
    assert "email" in res.json()["detail"].lower()

    # Token must NOT be in the DB
    result = await db_session.execute(
        select(InviteToken).where(InviteToken.email == "emailfail@example.com")
    )
    assert result.scalar_one_or_none() is None

    # But the access request status IS updated
    await db_session.refresh(req)
    assert req.status == "approved"


@pytest.mark.asyncio
async def test_approve_idempotent(db_session):
    """Approving an already-approved request returns 200 with already_approved status."""
    req = AccessRequest(email="idempotent_approve@example.com", status="pending")
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    params = _link("approve", req.id)

    with patch("src.api.routes.invite.send_user_invite_email", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            first = await c.get(f"/admin/approve/{req.id}", params=params)
            second = await c.get(f"/admin/approve/{req.id}", params=params)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "already_approved"


@pytest.mark.asyncio
async def test_deny_sets_status(db_session):
    """GET /admin/deny/{id} with valid sig sets AccessRequest.status='denied'."""
    req = AccessRequest(email="deny_me@example.com", status="pending")
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    params = _link("deny", req.id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get(f"/admin/deny/{req.id}", params=params)

    assert res.status_code == 200
    assert res.json()["status"] == "denied"

    await db_session.refresh(req)
    assert req.status == "denied"


@pytest.mark.asyncio
async def test_invite_token_consumed_on_register(db_session):
    """Full flow: approve → register with invite token → token marked consumed."""
    req = AccessRequest(email="fullflow@example.com", status="pending")
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    params = _link("approve", req.id)
    captured_token: list[str] = []

    async def _capture_email(to_email, raw_token, expires_at, base_url):
        captured_token.append(raw_token)

    with patch("src.api.routes.invite.send_user_invite_email", side_effect=_capture_email):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            approve_res = await c.get(f"/admin/approve/{req.id}", params=params)
    assert approve_res.status_code == 200

    raw_token = captured_token[0]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        reg_res = await c.post(
            "/auth/register",
            json={
                "email": "fullflow@example.com",
                "password": "SecurePass1!",
                "invite_token": raw_token,
            },
        )

    assert reg_res.status_code == 201

    # Token must be consumed
    import hashlib
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db_session.execute(
        select(InviteToken).where(InviteToken.token_hash == token_hash)
    )
    invite_row = result.scalar_one_or_none()
    assert invite_row is not None
    assert invite_row.consumed_at is not None, "invite token must be marked consumed after register"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["approve", "deny"])
async def test_expired_link_rejected(db_session, action):
    """RULE-SEC-07: a correctly signed link past its expiry returns 403 and changes nothing."""
    req = AccessRequest(email=f"expired_{action}@example.com", status="pending")
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    params = _link(action, req.id, ttl=timedelta(seconds=-1))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get(f"/admin/{action}/{req.id}", params=params)
    assert res.status_code == 403

    await db_session.refresh(req)
    assert req.status == "pending"


@pytest.mark.asyncio
async def test_tampered_expiry_rejected(db_session):
    """Extending exp without re-signing invalidates the signature."""
    req = AccessRequest(email="tamper@example.com", status="pending")
    db_session.add(req)
    await db_session.commit()
    await db_session.refresh(req)

    params = _link("approve", req.id, ttl=timedelta(seconds=-1))
    params["exp"] += 10**6
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get(f"/admin/approve/{req.id}", params=params)
    assert res.status_code == 403


def test_link_signature_ignores_jwt_secret(monkeypatch):
    """RULE-SEC-03: rotating JWT_SECRET must not invalidate admin links."""
    sig = make_hmac_sig("x")
    monkeypatch.setattr(settings, "jwt_secret", "a-completely-different-jwt-secret-32chars!!")
    assert verify_hmac_sig("x", sig)


def test_missing_admin_link_secret_fails_closed(monkeypatch):
    """No fallback to jwt_secret/app_secret when ADMIN_LINK_SECRET is unset."""
    monkeypatch.setattr(settings, "admin_link_secret", "")
    with pytest.raises(RuntimeError, match="ADMIN_LINK_SECRET"):
        make_hmac_sig("x")

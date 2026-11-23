"""Tests for JWT authentication (E12/E13).

Spec:
  A1. POST /auth/register with valid email+password → 200, returns access_token.
  A2. POST /auth/login with correct credentials → 200, returns access_token.
  A3. POST /auth/login with wrong password → 401.
  A4. Bearer JWT on protected route → 200.
  A5. No auth header on protected route → 401.
  A6. GET /health is public — no token needed.
"""

import pytest


@pytest.mark.asyncio
async def test_register_returns_token(client) -> None:
    """Valid registration returns an access_token (A1)."""
    res = await client.post(
        "/auth/register",
        json={"email": "new_auth_test@test.com", "password": "StrongPass1!"},
    )
    assert res.status_code in (200, 201)
    body = res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_correct_credentials(client) -> None:
    """Correct email+password returns access_token (A2)."""
    await client.post(
        "/auth/register",
        json={"email": "login_test@test.com", "password": "StrongPass1!"},
    )
    res = await client.post(
        "/auth/login",
        json={"email": "login_test@test.com", "password": "StrongPass1!"},
    )
    assert res.status_code == 200
    assert "access_token" in res.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client) -> None:
    """Wrong password → 401 (A3)."""
    await client.post(
        "/auth/register",
        json={"email": "wrongpw@test.com", "password": "StrongPass1!"},
    )
    res = await client.post(
        "/auth/login",
        json={"email": "wrongpw@test.com", "password": "WrongPassword!"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_health_public(client) -> None:
    """GET /health is accessible without any token (A6)."""
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_access_token_lifetime_honours_setting(monkeypatch) -> None:
    """ACCESS_TOKEN_EXPIRE_MINUTES (settings.access_token_expire_minutes) sets the JWT exp."""
    import uuid

    import jwt as pyjwt

    from src.core.auth import ALGORITHM, create_access_token
    from src.core.config import Settings, settings

    assert Settings().access_token_expire_minutes == 15  # default unchanged

    monkeypatch.setattr(settings, "access_token_expire_minutes", 1)
    payload = pyjwt.decode(
        create_access_token(uuid.uuid4()),
        settings.jwt_secret,
        algorithms=[ALGORITHM],
    )
    assert payload["exp"] - payload["iat"] == 60

    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "7")
    assert Settings().access_token_expire_minutes == 7

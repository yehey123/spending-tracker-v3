"""Auth routes: register, login, token refresh, Google OAuth, logout, sessions."""

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    decode_jwt,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    require_user,
    verify_password,
)
from src.core.config import settings
from src.core.oauth import fetch_google_userinfo, make_google_client
from src.db.session import get_db
from src.domain.models.user import OAuthAccount, RefreshToken, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_TOKEN_EXPIRE_DAYS = 7
REFRESH_TOKEN_ABSOLUTE_DAYS = 30
INVITE_TOKEN_EXPIRE_HOURS = 24
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


# ── Schemas ─────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = None
    invite_token: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_admin: bool = False


class SessionOut(BaseModel):
    session_id: uuid.UUID
    device_name: str | None
    created_at: datetime
    expires_at: datetime
    absolute_expires_at: datetime
    is_current: bool


# ── Helpers ──────────────────────────────────────────────────────────────────

def _refresh_cookie_kwargs() -> dict:
    return dict(
        key="refresh_token",
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth",
    )


def _access_cookie_kwargs() -> dict:
    return dict(
        key="access_token",
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _derive_device_name(request: Request) -> str | None:
    ua = request.headers.get("user-agent", "")
    return ua[:100] if ua else None


async def _issue_tokens(
    user: User,
    db: AsyncSession,
    response: Response,
    request: Request,
    device_name: str | None = None,
) -> TokenResponse:
    """Create a new session: access + refresh tokens, persist hash, set cookies."""
    session_id = uuid.uuid4()
    device = device_name or _derive_device_name(request)
    access_token = create_access_token(user.id, is_admin=user.is_admin, session_id=session_id)
    opaque, token_hash = generate_refresh_token()
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    absolute_expires_at = now + timedelta(days=REFRESH_TOKEN_ABSOLUTE_DAYS)
    db.add(RefreshToken(
        token_hash=token_hash,
        user_id=user.id,
        expires_at=expires_at,
        absolute_expires_at=absolute_expires_at,
        session_id=session_id,
        device_name=device[:100] if device else None,
    ))
    await db.commit()
    response.set_cookie(value=opaque, **_refresh_cookie_kwargs())
    response.set_cookie(value=access_token, **_access_cookie_kwargs())
    return TokenResponse(access_token=access_token, is_admin=user.is_admin)


async def _consume_invite_token(raw_token: str, db: AsyncSession) -> None:
    """Atomically validate and mark an invite token as consumed.

    Uses SELECT FOR UPDATE to prevent TOCTOU races.
    Raises HTTPException 400 on invalid, already-consumed, or expired tokens.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    result = await db.execute(
        text(
            "SELECT token_hash, consumed_at, expires_at "
            "FROM invite_tokens "
            "WHERE token_hash = :token_hash AND consumed_at IS NULL AND expires_at > now() "
            "FOR UPDATE"
        ),
        {"token_hash": token_hash},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=400, detail="Invalid, already-used, or expired invite token")

    await db.execute(
        text("UPDATE invite_tokens SET consumed_at = now() WHERE token_hash = :token_hash"),
        {"token_hash": token_hash},
    )


# ── Routes ───────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    if body.invite_token:
        await _consume_invite_token(body.invite_token, db)

    user = User(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    await db.flush()
    return await _issue_tokens(user, db, response, request)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or user.password_hash is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return await _issue_tokens(user, db, response, request, device_name=body.device_name)


@router.post("/token/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Rotate the refresh token; enforce absolute 30-day session cap."""
    opaque = request.cookies.get("refresh_token")
    if not opaque:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    token_hash = hash_refresh_token(opaque)
    now = datetime.now(tz=timezone.utc)

    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )
    rt = result.scalar_one_or_none()

    if rt is None:
        raise HTTPException(status_code=401, detail="Unknown refresh token")
    if rt.rotated_at is not None:
        raise HTTPException(status_code=401, detail="Refresh token already used")
    if rt.expires_at <= now:
        raise HTTPException(status_code=401, detail="Refresh token expired")

    if rt.absolute_expires_at <= now:
        await db.delete(rt)
        await db.commit()
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    rt.rotated_at = now

    result_user = await db.execute(select(User).where(User.id == rt.user_id))
    user = result_user.scalar_one()

    new_opaque, new_hash = generate_refresh_token()
    new_expires = min(
        now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        rt.absolute_expires_at,
    )
    new_rt = RefreshToken(
        token_hash=new_hash,
        user_id=rt.user_id,
        expires_at=new_expires,
        absolute_expires_at=rt.absolute_expires_at,
        session_id=rt.session_id,
        device_name=rt.device_name,
    )
    db.add(new_rt)
    await db.commit()

    access_token = create_access_token(
        user.id,
        is_admin=user.is_admin,
        session_id=rt.session_id,
    )
    response.set_cookie(value=new_opaque, **_refresh_cookie_kwargs())
    response.set_cookie(value=access_token, **_access_cookie_kwargs())
    return TokenResponse(access_token=access_token, is_admin=user.is_admin)


@router.get("/google")
async def google_login() -> dict:
    import httpx as _httpx
    async with _httpx.AsyncClient() as hc:
        discovery = (await hc.get(GOOGLE_DISCOVERY_URL)).json()
    async with make_google_client() as client:
        auth_url, state = client.create_authorization_url(discovery["authorization_endpoint"])
    return {"url": auth_url, "state": state}


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    userinfo = await fetch_google_userinfo(code, state)
    provider_sub = userinfo["sub"]
    email = userinfo.get("email", "")
    display_name = userinfo.get("name")

    oa_result = await db.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_sub == provider_sub,
        )
    )
    oa = oa_result.scalar_one_or_none()

    if oa:
        user_result = await db.execute(select(User).where(User.id == oa.user_id))
        user = user_result.scalar_one()
    else:
        user_result = await db.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()
        if user is None:
            user = User(email=email, display_name=display_name)
            db.add(user)
            await db.flush()
        db.add(OAuthAccount(provider="google", provider_sub=provider_sub, user_id=user.id))

    return await _issue_tokens(user, db, response, request)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_user),
) -> None:
    opaque = request.cookies.get("refresh_token")
    if opaque:
        token_hash = hash_refresh_token(opaque)
        now = datetime.now(tz=timezone.utc)
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(rotated_at=now)
        )
        await db.commit()
    response.delete_cookie(key="refresh_token", path="/auth")
    response.delete_cookie(key="access_token", path="/")


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> list[SessionOut]:
    """Return all active refresh_token sessions for the current user."""
    current_sid: uuid.UUID | None = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        try:
            payload = decode_jwt(auth_header[len("Bearer "):])
            sid_str = payload.get("sid")
            if sid_str:
                current_sid = uuid.UUID(sid_str)
        except Exception:
            pass

    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(RefreshToken)
        .where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.expires_at > now,
        )
        .order_by(RefreshToken.session_id, RefreshToken.expires_at.desc())
    )
    all_rows = result.scalars().all()

    seen: set[uuid.UUID] = set()
    rows = []
    for rt in all_rows:
        if rt.session_id not in seen:
            seen.add(rt.session_id)
            rows.append(rt)

    return [
        SessionOut(
            session_id=rt.session_id,
            device_name=rt.device_name,
            created_at=rt.absolute_expires_at - timedelta(days=REFRESH_TOKEN_ABSOLUTE_DAYS),
            expires_at=rt.expires_at,
            absolute_expires_at=rt.absolute_expires_at,
            is_current=(rt.session_id == current_sid),
        )
        for rt in rows
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> None:
    """Revoke a specific session. Allows self-revocation (logout from device)."""
    result = await db.execute(
        delete(RefreshToken)
        .where(
            RefreshToken.session_id == session_id,
            RefreshToken.user_id == current_user.id,
        )
        .returning(RefreshToken.session_id)
    )
    deleted = result.fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    await db.commit()

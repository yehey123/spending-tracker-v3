"""JWT + bcrypt authentication helpers and FastAPI dependency."""

import hashlib
import logging
import secrets
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.session import get_db
from src.domain.models.user import User

logger = logging.getLogger(__name__)

ACCESS_TOKEN_EXPIRE_MINUTES = 15
ALGORITHM = "HS256"


# ── Password helpers ────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT helpers ─────────────────────────────────────────────────────────────

def create_access_token(
    user_id: str | UUID,
    is_admin: bool = False,
    session_id: UUID | None = None,
) -> str:
    """Encode a JWT with sub, is_admin, jti, adm, sid, iat, exp claims."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "is_admin": is_admin,  # kept for middleware compat
        "adm": is_admin,
        "jti": str(_uuid.uuid4()),
        "sid": str(session_id) if session_id else None,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Return the full decoded payload dict or raise HTTPException 401.

    Used by E13 middleware which needs sub + is_admin from the same payload.
    """
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def decode_access_token(token: str) -> str:
    """Return user_id (str) or raise HTTPException 401."""
    return decode_jwt(token)["sub"]


# ── Refresh token helpers ───────────────────────────────────────────────────

def generate_refresh_token() -> tuple[str, str]:
    """Return (opaque_token, sha256_hex_hash).

    Store only the hash in the DB; send the opaque token to the client.
    """
    opaque = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(opaque.encode()).hexdigest()
    return opaque, token_hash


def hash_refresh_token(opaque: str) -> str:
    return hashlib.sha256(opaque.encode()).hexdigest()


# ── FastAPI dependency ──────────────────────────────────────────────────────

async def require_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode Bearer JWT (header or access_token cookie) and return the User row.

    Web clients send the access_token as an httponly cookie; native clients
    send Authorization: Bearer. Accept both.
    """
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[len("Bearer "):]
    else:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    user_id = decode_access_token(token)
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# Alias: routes importing require_token continue to compile without change.
# Runtime behaviour switches from shared-secret to per-user JWT.
require_token = require_user

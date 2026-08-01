"""Admin-only endpoints: user listing, activate/deactivate, resend-invite."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.bootstrap import BOOTSTRAP_KEY
from src.core.config import settings
from src.core.deps import require_admin
from src.core.email import send_user_invite_email
from src.db.session import get_db
from src.domain.models.invite_token import InviteToken
from src.domain.models.user import RefreshToken, SystemConfig, User

INVITE_TOKEN_EXPIRE_HOURS = 24  # must match auth.py constant

router = APIRouter(prefix="/admin", tags=["admin"])


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    is_admin: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserOut]
    total: int


@router.get("/users", response_model=UserListResponse)
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    result = await db.execute(select(User).order_by(User.created_at.asc()))
    users = result.scalars().all()
    return UserListResponse(users=list(users), total=len(users))


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account.")
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if not user.is_active:
        return user  # idempotent

    user.is_active = False
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users/{user_id}/reactivate", response_model=UserOut)
async def reactivate_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.is_active:
        return user  # idempotent

    user.is_active = True
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/resend-invite/{user_id}")
async def resend_invite(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Invalidate any existing invite token for this user and issue a fresh 24h token."""
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.is_active:
        raise HTTPException(status_code=400, detail="User is already active.")

    await db.execute(delete(InviteToken).where(InviteToken.email == user.email))

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(tz=timezone.utc) + timedelta(hours=INVITE_TOKEN_EXPIRE_HOURS)
    db.add(InviteToken(token_hash=token_hash, email=user.email, expires_at=expires_at))
    await db.commit()

    await send_user_invite_email(
        to_email=user.email,
        raw_token=raw_token,
        expires_at=expires_at,
        base_url=settings.app_base_url,
    )
    return {"status": "sent", "email": user.email, "expires_hours": INVITE_TOKEN_EXPIRE_HOURS}


@router.post("/bootstrap")
async def bootstrap_admin(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """One-time endpoint: promote first user to admin when no admin exists.

    Public — no auth required. Becomes a no-op once any admin exists.
    """
    already = (await db.execute(
        select(SystemConfig).where(SystemConfig.key == BOOTSTRAP_KEY)
    )).scalar_one_or_none()
    if already and already.value == "true":
        raise HTTPException(status_code=409, detail="Admin already exists.")

    first = (await db.execute(
        select(User).order_by(User.created_at.asc()).limit(1)
    )).scalar_one_or_none()
    if first is None:
        raise HTTPException(status_code=404, detail="No users registered yet.")

    first.is_admin = True
    db.add(SystemConfig(key=BOOTSTRAP_KEY, value="true"))
    await db.commit()
    return {"promoted": str(first.id), "email": first.email}

"""FastAPI dependencies for authenticated user access."""

from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.domain.models.user import User


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the JWT subject (set by UserContextMiddleware) to a User ORM row.

    Raises HTTP 401 if no valid JWT was presented.
    Raises HTTP 403 if the user UUID from the token does not exist in the DB.
    """
    user_id_str = getattr(request.state, 'user_id', None)
    if user_id_str is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Malformed user identity in token.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=403, detail="User account not found.")

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Account deactivated. Contact your administrator.",
        )

    return user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require the caller to be an active admin. Raises 403 otherwise."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require the requesting user to be an admin."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user

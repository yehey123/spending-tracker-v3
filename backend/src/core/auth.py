"""Shared-secret API token authentication dependency."""

import hmac
import logging

from fastapi import Header, HTTPException

from src.core.config import settings

logger = logging.getLogger(__name__)

_unauthenticated_warning_emitted = False


def _extract_token(x_api_token: str | None, authorization: str | None) -> str | None:
    if x_api_token:
        return x_api_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[len("Bearer "):]
    return None


async def require_token(
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    """FastAPI dependency enforcing the shared-secret API token.

    Auth is disabled when `settings.api_token` is empty — a one-time warning
    is logged per process in that case. Otherwise the token must be supplied
    via the `X-API-Token` header or an `Authorization: Bearer <token>` header
    and match `settings.api_token` (constant-time comparison).
    """
    global _unauthenticated_warning_emitted

    if settings.api_token == "":
        if not _unauthenticated_warning_emitted:
            logger.warning("api_token is not set — API is running unauthenticated")
            _unauthenticated_warning_emitted = True
        return

    token = _extract_token(x_api_token, authorization)
    if token is None or not hmac.compare_digest(token, settings.api_token):
        raise HTTPException(status_code=401, detail="Invalid or missing API token")

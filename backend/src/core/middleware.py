"""Per-request JWT extraction middleware — sets request.state.user_id and is_admin."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.auth import decode_jwt

PUBLIC_PREFIXES = (
    "/health",
    "/auth/",
)


class UserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request.state.user_id = None
        request.state.is_admin = False

        if any(request.url.path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[len("Bearer "):]
            try:
                payload = decode_jwt(token)
                request.state.user_id = payload.get("sub")
                request.state.is_admin = payload.get("is_admin", False)
            except Exception:
                # Middleware does not reject — the route dependency does.
                pass

        return await call_next(request)

"""Google OAuth 2.0 client using Authlib."""

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from src.core.config import settings

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


def make_google_client() -> AsyncOAuth2Client:
    """Return a fresh Authlib OAuth2 client configured for Google OIDC."""
    return AsyncOAuth2Client(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scope="openid email profile",
        redirect_uri=settings.google_redirect_uri,
    )


async def fetch_google_userinfo(code: str, state: str) -> dict:
    """Exchange the authorization code for tokens and return the userinfo dict.

    Returns keys: sub, email, name (display_name candidate).
    """
    async with httpx.AsyncClient() as hc:
        discovery = (await hc.get(GOOGLE_DISCOVERY_URL)).json()

    token_endpoint = discovery["token_endpoint"]
    userinfo_endpoint = discovery["userinfo_endpoint"]

    async with make_google_client() as client:
        token = await client.fetch_token(token_endpoint, code=code, state=state)
        resp = await client.get(userinfo_endpoint, token=token)
        resp.raise_for_status()
        return resp.json()

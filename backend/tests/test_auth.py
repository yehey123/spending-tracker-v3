"""Tests for shared-secret API token authentication (src/core/auth.py).

Spec provenance:
  A1. api_token == "" → auth disabled, protected route reachable with no header.
  A2. Correct token in X-API-Token → 200.
  A3. Correct token in Authorization: Bearer → 200.
  A4. Wrong token → 401, detail "Invalid or missing API token".
  A5. No header at all when token set → 401.
  A6. /health always reachable even when api_token is set.
"""

import pytest

from src.core.config import settings as _settings

_PROTECTED_ROUTE = "/categories"
_TEST_TOKEN = "super-secret-test-token-abc"


@pytest.mark.asyncio
async def test_auth_disabled_when_token_empty(client, monkeypatch) -> None:
    """Empty api_token disables auth — protected route accessible with no header (A1)."""
    monkeypatch.setattr(_settings, "api_token", "")
    res = await client.get(_PROTECTED_ROUTE)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_correct_x_api_token_header_accepted(client, monkeypatch) -> None:
    """Correct token in X-API-Token header → request proceeds (A2)."""
    monkeypatch.setattr(_settings, "api_token", _TEST_TOKEN)
    res = await client.get(_PROTECTED_ROUTE, headers={"X-API-Token": _TEST_TOKEN})
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_correct_bearer_token_accepted(client, monkeypatch) -> None:
    """Correct token in Authorization: Bearer → request proceeds (A3)."""
    monkeypatch.setattr(_settings, "api_token", _TEST_TOKEN)
    res = await client.get(
        _PROTECTED_ROUTE, headers={"Authorization": f"Bearer {_TEST_TOKEN}"}
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_wrong_token_returns_401(client, monkeypatch) -> None:
    """Wrong token value → 401 with exact detail message (A4)."""
    monkeypatch.setattr(_settings, "api_token", _TEST_TOKEN)
    res = await client.get(_PROTECTED_ROUTE, headers={"X-API-Token": "wrong-value"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid or missing API token"


@pytest.mark.asyncio
async def test_no_header_returns_401(client, monkeypatch) -> None:
    """No auth header when api_token is set → 401 with exact detail message (A5)."""
    monkeypatch.setattr(_settings, "api_token", _TEST_TOKEN)
    res = await client.get(_PROTECTED_ROUTE)
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid or missing API token"


@pytest.mark.asyncio
async def test_health_reachable_with_no_token_when_auth_enabled(client, monkeypatch) -> None:
    """GET /health is accessible with no token even when api_token is set (A6)."""
    monkeypatch.setattr(_settings, "api_token", _TEST_TOKEN)
    res = await client.get("/health")
    assert res.status_code == 200

"""Tests for ExchangeRateService — async SQLite cache + Frankfurter API."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.exchange_rate import ExchangeRateService
import src.domain.services.exchange_rate as _er_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int, body: dict) -> MagicMock:
    """Build a mock httpx Response-like object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    # raise_for_status: raise only on 4xx/5xx
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response

        resp.raise_for_status.side_effect = HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(spec=Request),
            response=MagicMock(spec=Response),
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _patch_get(mock_resp: MagicMock):
    """Context-manager patch: httpx.AsyncClient.get → returns mock_resp."""
    return patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(return_value=mock_resp),
    )


async def _make_service(tmp_path) -> ExchangeRateService:
    """Create and initialise a service backed by a temp SQLite file."""
    svc = ExchangeRateService()
    svc._db_path = str(tmp_path / "rates.db")
    await svc.init_db()
    return svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_get_rate_same_currency(tmp_path):
    svc = await _make_service(tmp_path)
    result = await svc.get_rate("2024-01-15", "USD", "USD")
    assert result == 1.0


async def test_get_rate_cache_hit_no_http(tmp_path):
    """If rate already in DB, no HTTP call is made."""
    svc = await _make_service(tmp_path)
    # Pre-populate the cache
    await svc._upsert_rate("2024-01-15", "USD", "EUR", 0.92, "2024-01-15T00:00:00")

    with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
        result = await svc.get_rate("2024-01-15", "USD", "EUR")

    assert result == pytest.approx(0.92)
    mock_get.assert_not_called()


async def test_get_rate_cache_miss_fetches_and_stores(tmp_path):
    """On cache miss, Frankfurter is called and both directions are stored."""
    svc = await _make_service(tmp_path)
    mock_resp = _mock_response(200, {"rates": {"EUR": 0.92}})

    with _patch_get(mock_resp):
        result = await svc.get_rate("2024-01-15", "USD", "EUR")

    assert result == pytest.approx(0.92)

    # Forward direction stored
    forward = await svc._cache_lookup("2024-01-15", "USD", "EUR")
    assert forward == pytest.approx(0.92)

    # Reverse direction stored
    reverse = await svc._cache_lookup("2024-01-15", "EUR", "USD")
    assert reverse == pytest.approx(1.0 / 0.92)


async def test_get_rate_frankfurter_404_returns_none(tmp_path):
    """A 404 from Frankfurter should return None, not raise."""
    svc = await _make_service(tmp_path)
    mock_resp = _mock_response(404, {})

    with _patch_get(mock_resp):
        result = await svc.get_rate("1900-01-01", "USD", "EUR")

    assert result is None


async def test_get_rate_network_error_returns_none(tmp_path):
    """A network error should return None, not raise."""
    import httpx

    svc = await _make_service(tmp_path)

    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(side_effect=httpx.RequestError("timeout")),
    ):
        result = await svc.get_rate("2024-01-15", "USD", "EUR")

    assert result is None


async def test_prefetch_range_upserts_all_dates_both_directions(tmp_path):
    """prefetch_range stores all API dates in both directions."""
    svc = await _make_service(tmp_path)
    api_body = {
        "rates": {
            "2024-01-15": {"EUR": 0.92},
            "2024-01-16": {"EUR": 0.91},
        }
    }
    mock_resp = _mock_response(200, api_body)

    with _patch_get(mock_resp):
        summary = await svc.prefetch_range("USD", "EUR", "2024-01-15", "2024-01-16")

    assert summary["fetched"] == 2
    assert summary["skipped_cached"] == 0
    assert summary["unavailable"] == 0
    assert summary["from_currency"] == "USD"
    assert summary["to_currency"] == "EUR"

    # Spot-check both directions for one date
    assert await svc._cache_lookup("2024-01-15", "USD", "EUR") == pytest.approx(0.92)
    assert await svc._cache_lookup("2024-01-15", "EUR", "USD") == pytest.approx(1.0 / 0.92)


async def test_prefetch_range_skips_cached_dates(tmp_path):
    """Dates already in DB are counted as skipped_cached and not re-fetched."""
    svc = await _make_service(tmp_path)
    # Pre-seed one date
    await svc._upsert_rate("2024-01-15", "USD", "EUR", 0.92, "2024-01-01T00:00:00")

    api_body = {
        "rates": {
            "2024-01-15": {"EUR": 0.95},  # already cached — should skip
            "2024-01-16": {"EUR": 0.91},  # new
        }
    }
    mock_resp = _mock_response(200, api_body)

    with _patch_get(mock_resp):
        summary = await svc.prefetch_range("USD", "EUR", "2024-01-15", "2024-01-16")

    assert summary["fetched"] == 1
    assert summary["skipped_cached"] == 1

    # The pre-seeded value must NOT have been overwritten
    assert await svc._cache_lookup("2024-01-15", "USD", "EUR") == pytest.approx(0.92)


async def test_get_supported_currencies_returns_dict(tmp_path):
    """get_supported_currencies returns the dict from Frankfurter."""
    # Reset module-level cache to ensure a fresh fetch
    _er_module._currencies_cache = {}

    svc = await _make_service(tmp_path)
    mock_resp = _mock_response(200, {"USD": "US Dollar", "EUR": "Euro"})

    with _patch_get(mock_resp):
        result = await svc.get_supported_currencies()

    assert result == {"USD": "US Dollar", "EUR": "Euro"}


async def test_get_supported_currencies_uses_in_process_cache(tmp_path):
    """Second call uses in-process cache — no second HTTP request."""
    _er_module._currencies_cache = {}

    svc = await _make_service(tmp_path)
    mock_resp = _mock_response(200, {"USD": "US Dollar", "EUR": "Euro"})

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_resp)) as mock_get:
        await svc.get_supported_currencies()
        await svc.get_supported_currencies()

    # HTTP called exactly once
    assert mock_get.call_count == 1

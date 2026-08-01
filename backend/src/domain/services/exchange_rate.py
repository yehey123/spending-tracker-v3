"""Exchange rate service — async SQLite cache backed by Frankfurter public API."""

from __future__ import annotations

import datetime
from datetime import UTC
import logging
from typing import Any

import aiosqlite
import httpx
from fastapi import HTTPException

from src.core.config import settings

logger = logging.getLogger(__name__)

# Module-level in-process currency cache; repopulated on each process start if empty.
_currencies_cache: dict[str, str] = {}

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS exchange_rates (
    date TEXT NOT NULL,
    base_currency TEXT NOT NULL,
    quote_currency TEXT NOT NULL,
    rate REAL NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (date, base_currency, quote_currency)
)
"""

_FRANKFURTER_BASE = "https://api.frankfurter.app"


class ExchangeRateService:
    """Async service for lazily populating and querying a local exchange-rate SQLite cache."""

    def __init__(self) -> None:
        self._db_path = settings.rates_db_path

    # ------------------------------------------------------------------
    # DB lifecycle
    # ------------------------------------------------------------------

    async def init_db(self) -> None:
        """Create the exchange_rates table if it does not yet exist (idempotent)."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE_SQL)
            await db.commit()

    # ------------------------------------------------------------------
    # Core rate lookup
    # ------------------------------------------------------------------

    async def get_rate(self, date: str, base: str, quote: str) -> float | None:
        """Return the exchange rate for base→quote on the given date (YYYY-MM-DD).

        Resolution order:
          1. base == quote → 1.0
          2. SQLite cache hit → return cached rate
          3. Frankfurter API → store both directions, return rate
          4. Frankfurter 404 / network error → return None
        """
        if base == quote:
            return 1.0

        cached = await self._cache_lookup(date, base, quote)
        if cached is not None:
            return cached

        # Fetch from Frankfurter
        url = f"{_FRANKFURTER_BASE}/{date}?from={base}&to={quote}"
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                resp = await client.get(url)
        except httpx.RequestError as exc:
            logger.warning("Frankfurter network error for %s/%s on %s: %s", base, quote, date, exc)
            return None

        if resp.status_code == 404:
            logger.debug("Frankfurter 404 for %s/%s on %s", base, quote, date)
            return None

        if resp.status_code != 200:
            logger.warning(
                "Frankfurter unexpected status %s for %s/%s on %s",
                resp.status_code,
                base,
                quote,
                date,
            )
            return None

        data: dict[str, Any] = resp.json()
        rates: dict[str, float] = data.get("rates", {})
        rate = rates.get(quote)
        if rate is None:
            logger.warning("Frankfurter response missing rate for %s on %s→%s", date, base, quote)
            return None

        fetched_at = datetime.datetime.now(UTC).isoformat()
        await self._upsert_rate(date, base, quote, rate, fetched_at)
        if rate != 0:
            await self._upsert_rate(date, quote, base, 1.0 / rate, fetched_at)

        return rate

    # ------------------------------------------------------------------
    # Supported currencies
    # ------------------------------------------------------------------

    async def get_supported_currencies(self) -> dict[str, str]:
        """Return map of ISO-4217 code → currency name.

        Result is cached in-process; re-fetched from Frankfurter on next process start.
        On network error: returns in-process cache if non-empty, else raises HTTP 503.
        """
        global _currencies_cache  # noqa: PLW0603

        if _currencies_cache:
            return dict(_currencies_cache)

        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                resp = await client.get(f"{_FRANKFURTER_BASE}/currencies")
            resp.raise_for_status()
            result: dict[str, str] = resp.json()
            _currencies_cache = result
            return dict(result)
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.error("Failed to fetch supported currencies from Frankfurter: %s", exc)
            if _currencies_cache:
                return dict(_currencies_cache)
            raise HTTPException(
                status_code=503,
                detail="Exchange rate service unavailable — could not fetch supported currencies.",
            ) from exc

    # ------------------------------------------------------------------
    # Bulk prefetch
    # ------------------------------------------------------------------

    async def prefetch_range(
        self, base: str, quote: str, start: str, end: str
    ) -> dict[str, Any]:
        """Fetch and cache the full time-series for base→quote in [start, end].

        Uses the Frankfurter time-series endpoint in a single request.
        Returns summary dict with fetched/skipped_cached counts.
        Raises HTTP 503 on Frankfurter error.
        """
        url = f"{_FRANKFURTER_BASE}/{start}..{end}?from={base}&to={quote}"
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url)
            resp.raise_for_status()
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.error(
                "Frankfurter prefetch failed for %s→%s [%s..%s]: %s", base, quote, start, end, exc
            )
            raise HTTPException(
                status_code=503,
                detail=f"Exchange rate service unavailable: {exc}",
            ) from exc

        data: dict[str, Any] = resp.json()
        # Frankfurter time-series: {"rates": {"2024-01-02": {"GBP": 0.87}, ...}}
        rates: dict[str, dict[str, float]] = data.get("rates", {})

        # Determine which dates are already cached so we can compute skipped_cached
        all_dates = set(rates.keys())
        already_cached = await self._cached_dates(base, quote, all_dates)

        fetched_at = datetime.datetime.now(UTC).isoformat()
        fetched = 0
        skipped_cached = 0

        async with aiosqlite.connect(self._db_path) as db:
            for date, day_rates in rates.items():
                rate = day_rates.get(quote)
                if rate is None:
                    continue
                if date in already_cached:
                    skipped_cached += 1
                    continue
                await db.execute(
                    "INSERT OR REPLACE INTO exchange_rates "
                    "(date, base_currency, quote_currency, rate, fetched_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (date, base, quote, rate, fetched_at),
                )
                if rate != 0:
                    await db.execute(
                        "INSERT OR REPLACE INTO exchange_rates "
                        "(date, base_currency, quote_currency, rate, fetched_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (date, quote, base, 1.0 / rate, fetched_at),
                    )
                fetched += 1
            await db.commit()

        return {
            "from_currency": base,
            "to_currency": quote,
            "start_date": start,
            "end_date": end,
            "fetched": fetched,
            "skipped_cached": skipped_cached,
            "unavailable": 0,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _cache_lookup(self, date: str, base: str, quote: str) -> float | None:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT rate FROM exchange_rates "
                "WHERE date=? AND base_currency=? AND quote_currency=?",
                (date, base, quote),
            ) as cursor:
                row = await cursor.fetchone()
        return row[0] if row is not None else None

    async def _upsert_rate(
        self, date: str, base: str, quote: str, rate: float, fetched_at: str
    ) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO exchange_rates "
                "(date, base_currency, quote_currency, rate, fetched_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (date, base, quote, rate, fetched_at),
            )
            await db.commit()

    async def _cached_dates(self, base: str, quote: str, dates: set[str]) -> set[str]:
        """Return the subset of `dates` already present in the cache for base→quote."""
        if not dates:
            return set()
        placeholders = ",".join("?" * len(dates))
        params = list(dates) + [base, quote]
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                f"SELECT date FROM exchange_rates "  # noqa: S608
                f"WHERE date IN ({placeholders}) "
                f"AND base_currency=? AND quote_currency=?",
                params,
            ) as cursor:
                rows = await cursor.fetchall()
        return {row[0] for row in rows}


# Module-level singleton
exchange_rate_service = ExchangeRateService()

#!/usr/bin/env python3
"""
CI script: fetch Frankfurter exchange rates and store in exchange_rates.db.

Modes:
  - BACKFILL=true  (or empty table): full backfill 1999-01-04 → today
  - BACKFILL=false (default):        incremental from MAX(date)+1 → today
"""

import os
import sqlite3
import sys
from datetime import date, timedelta

import httpx

DB_PATH = os.environ.get("DB_PATH", "exchange_rates.db")
BACKFILL_START = date(1999, 1, 4)
FRANKFURTER_BASE = "https://api.frankfurter.app"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS exchange_rates (
  date TEXT NOT NULL,
  base_currency TEXT NOT NULL,
  quote_currency TEXT NOT NULL,
  rate REAL NOT NULL,
  fetched_at TEXT NOT NULL,
  PRIMARY KEY (date, base_currency, quote_currency)
)
"""

UPSERT_SQL = """
INSERT OR REPLACE INTO exchange_rates
  (date, base_currency, quote_currency, rate, fetched_at)
VALUES (?, ?, ?, ?, ?)
"""


def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()
    return conn


def max_date(conn: sqlite3.Connection) -> date | None:
    row = conn.execute("SELECT MAX(date) FROM exchange_rates").fetchone()
    if row and row[0]:
        return date.fromisoformat(row[0])
    return None


def is_empty(conn: sqlite3.Connection) -> bool:
    return max_date(conn) is None


def determine_range(conn: sqlite3.Connection) -> tuple[date, date] | None:
    """Return (start, end) date range to fetch, or None if already up-to-date."""
    today = date.today()
    backfill_env = os.environ.get("BACKFILL", "false").lower()

    if backfill_env == "true" or is_empty(conn):
        start = BACKFILL_START
    else:
        last = max_date(conn)
        start = last + timedelta(days=1)

    end = today
    if start > end:
        return None
    return start, end


def fetch_rates(start: date, end: date) -> dict[str, dict[str, float]]:
    """
    Fetch rates from Frankfurter.  Returns {date_str: {currency: rate}}.
    Uses single-date endpoint when start == end (time-series requires start < end).
    """
    if start == end:
        url = f"{FRANKFURTER_BASE}/{start.isoformat()}?from=USD"
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        # Single-date response: {"rates": {"EUR": 0.91, ...}} — no date key
        return {start.isoformat(): data["rates"]}
    else:
        url = f"{FRANKFURTER_BASE}/{start.isoformat()}..{end.isoformat()}?from=USD"
        resp = httpx.get(url, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        # Time-series response: {"rates": {"YYYY-MM-DD": {"EUR": 0.91, ...}, ...}}
        return data["rates"]


def store_rates(
    conn: sqlite3.Connection,
    rates_by_date: dict[str, dict[str, float]],
    fetched_at: str,
) -> int:
    """Insert forward and reverse rate pairs. Returns number of rate pairs stored."""
    pairs_stored = 0
    for date_str, quote_map in rates_by_date.items():
        for quote, rate in quote_map.items():
            # Forward: USD → quote
            conn.execute(UPSERT_SQL, (date_str, "USD", quote, rate, fetched_at))
            # Reverse: quote → USD
            conn.execute(UPSERT_SQL, (date_str, quote, "USD", 1.0 / rate, fetched_at))
            pairs_stored += 2
    conn.commit()
    return pairs_stored


def main() -> None:
    from datetime import datetime, timezone

    conn = open_db(DB_PATH)

    date_range = determine_range(conn)
    if date_range is None:
        print("Already up to date.")
        conn.close()
        sys.exit(0)

    start, end = date_range

    try:
        rates_by_date = fetch_rates(start, end)
    except httpx.HTTPStatusError as exc:
        print(
            f"Frankfurter API error {exc.response.status_code}: {exc.response.text}",
            file=sys.stderr,
        )
        conn.close()
        sys.exit(1)
    except httpx.RequestError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        conn.close()
        sys.exit(1)

    fetched_at = datetime.now(timezone.utc).isoformat()
    n_dates = len(rates_by_date)
    n_pairs = store_rates(conn, rates_by_date, fetched_at)
    conn.close()

    print(f"Fetched {n_dates} dates, {n_pairs} rate pairs stored.")


if __name__ == "__main__":
    main()

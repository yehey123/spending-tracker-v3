# Currency Contract — Spending Tracker

Covers all schema, API, and behavioral changes introduced by E7 (Multi-Currency Support).
Read alongside `api.md` and `db-schema.md` — this file lists only additive or modified contracts.

---

## DB Schema Additions

### Modified: `app_settings`

New column:

| Column | Type | Constraints | Default |
|---|---|---|---|
| home_currency | VARCHAR(3) | NULL | NULL |

`NULL` means "not yet configured." The application layer treats null as "no conversion available."

### Modified: `transactions`

New column:

| Column | Type | Constraints | Default |
|---|---|---|---|
| currency | VARCHAR(3) | NULL | NULL |

`NULL` means "same as home currency — no conversion needed." ISO 4217 code when set (e.g., `"USD"`, `"EUR"`, `"PHP"`).

### New: `exchange_rates`

| Column | Type | Constraints | Default |
|---|---|---|---|
| id | INTEGER | PK, auto-increment | — |
| date | DATE | NOT NULL | — |
| base_currency | VARCHAR(3) | NOT NULL | — |
| quote_currency | VARCHAR(3) | NOT NULL | — |
| rate | NUMERIC(18,6) | NOT NULL, CHECK (rate > 0) | — |
| fetched_at | TIMESTAMP | NOT NULL | `NOW()` |

Indexes:
- `uq_exchange_rates_date_base_quote` — UNIQUE on `(date, base_currency, quote_currency)` — prevents duplicate fetches
- `ix_exchange_rates_date` — for range queries during prefetch

Notes:
- Rates are stored in both directions when fetched: `USD→PHP` and `PHP→USD` (1/rate). This halves future lookups.
- Rate is keyed to the **requested date**, not the ECB effective date (weekends/holidays resolve to the nearest prior business day at fetch time; the resolved rate is stored under the originally requested date).

---

## API — Modified Endpoints

### GET /settings

Response 200 — adds `home_currency`:
```json
{
  "ocr_provider": "tesseract",
  "anthropic_api_key_set": false,
  "openai_api_key_set": false,
  "home_currency": "PHP"
}
```

`home_currency` is `null` when not yet set.

### PUT /settings

Request body — adds optional `home_currency`:
```json
{
  "ocr_provider": "tesseract",
  "home_currency": "PHP"
}
```

Validation:
- `home_currency`: optional; if provided, must be a 3-letter uppercase string present in the Frankfurter supported-currencies list. Send `null` to explicitly unset.

Response 200: same shape as GET /settings.
Response 422: `{ "detail": "Unsupported currency code: 'XYZ'. Check /exchange-rates/supported." }`

---

### GET /transactions

Response shape — adds `currency` field to each item:
```json
{
  "id": 42,
  "date": "2024-03-05T00:00:00Z",
  "amount": "72.50",
  "currency": "USD",
  "description": "Amazon",
  "direction": "debit",
  "category_id": 3,
  "category": { "id": 3, "name": "Shopping", "color": "#F59E0B" },
  "statement_id": null
}
```

`currency: null` means the transaction is in the home currency.

#### Optional: `?with_conversion=true` (Story 7.5)

When present, each item additionally contains:
```json
{
  "converted_amount": "4250.00",
  "converted_currency": "PHP"
}
```

Both fields are `null` when:
- `currency` is null (already home currency)
- `currency == home_currency`
- No rate is available for the transaction's date (unconverted)

### POST /transactions

Request body — adds optional `currency`:
```json
{
  "date": "2024-03-05T00:00:00Z",
  "amount": "72.50",
  "currency": "USD",
  "description": "Amazon",
  "direction": "debit",
  "category_id": null
}
```

Validation:
- `currency`: optional; 3-letter uppercase ISO 4217 code, or omit/`null` for home-currency assumption.

Response 201: Full transaction object (same shape as GET item with `currency` field).

### PATCH /transactions/{id}

Request body — adds optional `currency`:
```json
{
  "currency": "USD"
}
```

Send `"currency": null` to reset to home-currency assumption.

---

### GET /analytics/by-category

Query params — adds optional `display_currency`:
- `display_currency` (string, optional): ISO 4217 code. Defaults to `home_currency` from settings. Overrides for ad-hoc comparison.

Response 200 — adds `display_currency` and `unconverted_count`:
```json
{
  "month": "2024-03",
  "display_currency": "PHP",
  "total_debit": "18450.00",
  "unconverted_count": 2,
  "breakdown": [
    {
      "category_id": 1,
      "category_name": "Food & Dining",
      "color": "#F59E0B",
      "amount": "5200.00",
      "percent": 28.2
    }
  ]
}
```

`unconverted_count` is the number of transactions whose rate was unavailable. These are excluded from totals and breakdown amounts.

**When `home_currency` is null and no `?display_currency=` is provided:**
```json
{
  "month": "2024-03",
  "display_currency": null,
  "totals_available": false,
  "unconverted_count": null,
  "detail": "Set home_currency in /settings to enable currency aggregation.",
  "breakdown": [
    {
      "category_id": 1,
      "category_name": "Food & Dining",
      "color": "#F59E0B",
      "amount": null,
      "percent": null
    }
  ]
}
```

HTTP status remains **200** — this is an advisory state, not an error.

### GET /analytics/cash-flow

Same additions as by-category: `display_currency`, `unconverted_count` in the root of the response. Each month object is unchanged in structure; amounts are in `display_currency`.

---

## API — New Endpoints

### GET /exchange-rates/supported

Returns the list of ISO 4217 codes supported by the rate cache (i.e., the Frankfurter currency list). Response is fetched from Frankfurter once and cached in memory per process restart.

Response 200:
```json
{
  "currencies": {
    "USD": "United States Dollar",
    "EUR": "Euro",
    "PHP": "Philippine Peso",
    "GBP": "British Pound",
    "JPY": "Japanese Yen"
  }
}
```

Response 503 (if Frankfurter unreachable and no in-process cache):
```json
{ "detail": "Currency list unavailable. Check network connectivity or retry." }
```

---

### POST /exchange-rates/prefetch

Pre-seeds the local cache for a currency pair over a date range. Designed for users who want to operate fully offline after a one-time seed.

Request body:
```json
{
  "from_currency": "USD",
  "to_currency": "PHP",
  "start_date": "2015-01-01",
  "end_date": "2024-12-31"
}
```

Validation:
- `from_currency`, `to_currency`: required, must be in supported list
- `start_date`, `end_date`: required, ISO 8601 date strings; `start_date ≤ end_date`; maximum range 10 years per call (to limit timeouts)
- `start_date` before 1999-01-04: accepted, but rates before this date will not be found in Frankfurter (ECB data starts 1999-01-04); those dates will be absent in the cache and will surface as `unconverted_count` in analytics

Behavior:
- Fetches daily rates from Frankfurter for the range; skips dates already in cache
- Stores both directions (from→to and to→from as 1/rate)
- Long-running: runs synchronously but uses async HTTP; caller should expect 5–30 s for multi-year ranges

Response 200:
```json
{
  "from_currency": "USD",
  "to_currency": "PHP",
  "start_date": "2015-01-01",
  "end_date": "2024-12-31",
  "fetched": 2610,
  "skipped_cached": 0,
  "unavailable": 3
}
```

- `fetched`: rates successfully stored
- `skipped_cached`: dates already in cache
- `unavailable`: dates where Frankfurter returned no rate (weekends without data, pre-1999)

Response 422: Invalid currency code or date range.
Response 503: Frankfurter unreachable.

---

## Rate-Unavailable State Machine

```
Need rate(date, from, to)
       │
       ▼
 Cache hit? ──yes──▶ use rate
       │
      no
       │
       ▼
 Fetch Frankfurter ──success──▶ store in cache ──▶ use rate
       │
      fail (404 / network error / pre-1999)
       │
       ▼
 rate = UNAVAILABLE
       │
       ▼
 Transaction counted in unconverted_count
 Transaction amount NOT included in analytics totals
 Transaction IS still returned in GET /transactions (original amount + currency intact)
```

**Never**: zero the amount, assume 1:1, or return a 5xx on the analytics endpoint due to a missing rate.

---

---

## CI Pipeline — Exchange Rate Artifact (Story 7.6)

### Workflow: `.github/workflows/rates-update.yml`

```
Trigger: schedule cron '0 3 * * *' (03:00 UTC daily)
         workflow_dispatch { backfill: bool = false }

Permissions: contents: write  (release asset upload)

Steps:
  1. Download existing exchange_rates.db from rates-latest release
       curl -fL <GH_RELEASES_URL>/exchange_rates.db -o exchange_rates.db
       || touch exchange_rates.db   # start fresh if release doesn't exist yet
  2. Run .github/scripts/update_rates.py
       env BACKFILL=true|false
  3. Upload exchange_rates.db as asset on tag rates-latest
       (tag is created if absent; force-moved if it exists)
       release name: "Exchange Rate Cache — auto-updated daily"
       prerelease: true
```

### Script: `.github/scripts/update_rates.py`

Dependencies: `httpx` (sync), `sqlite3` (stdlib)

```
Schema (created if absent):
  CREATE TABLE IF NOT EXISTS exchange_rates (
    date          TEXT NOT NULL,        -- ISO 8601 YYYY-MM-DD
    base_currency TEXT NOT NULL,        -- always "USD"
    quote_currency TEXT NOT NULL,
    rate          REAL NOT NULL,
    fetched_at    TEXT NOT NULL,        -- ISO 8601 timestamp
    PRIMARY KEY (date, base_currency, quote_currency)
  );

Logic:
  IF backfill == true OR table is empty:
    fetch = GET https://api.frankfurter.app/1999-01-04..{today}?from=USD
    # Returns: { "rates": { "YYYY-MM-DD": { "EUR": 0.88, "PHP": 56.1, ... }, ... } }
    upsert all rows (ON CONFLICT REPLACE)
    also upsert reverse pairs: (date, X, USD, 1/rate)
  ELSE (incremental):
    latest_in_db = SELECT MAX(date) FROM exchange_rates
    fetch = GET https://api.frankfurter.app/{latest_in_db+1d}..{today}?from=USD
    upsert new rows + reverse pairs

Error handling:
  Frankfurter 404 on a date range → skip silently (weekend / holiday gap; nearest prior rate
  is already in DB and the on-demand fallback in the backend handles it)
  Frankfurter 5xx / network error → exit non-zero → GHA marks the run failed; last good DB
  artifact is NOT replaced (upload step only runs on prior step success)
```

Artifact size estimate: ~9,125 dates × 32 pairs × 2 directions = ~584k rows. SQLite at ~60 bytes/row ≈ **35 MB** uncompressed. Acceptable as a release asset.

---

### Docker Compose Bootstrap

`docker-compose.yml` additions:

```yaml
services:
  rates-init:
    image: alpine/curl:8
    volumes:
      - exchange_rates_data:/data/rates
    environment:
      RATES_DB_URL: ${RATES_DB_URL:-https://github.com/<owner>/spending-tracker/releases/download/rates-latest/exchange_rates.db}
    entrypoint: >
      sh -c "
        if [ ! -s /data/rates/exchange_rates.db ]; then
          echo 'Bootstrapping exchange rate DB...';
          curl -fL --retry 3 $$RATES_DB_URL -o /data/rates/exchange_rates.db;
        else
          echo 'Exchange rate DB already present, skipping download.';
        fi
      "
    restart: "no"

  backend:
    depends_on:
      db:
        condition: service_healthy
      rates-init:
        condition: service_completed_successfully
```

New named volume:
```yaml
volumes:
  postgres_data:
  exchange_rates_data:   # separate from postgres_data; rates are shareable/replaceable
```

`RATES_DB_URL` in `.env.example`:
```
# Exchange rate DB bootstrap URL. Override to point at a mirror or local path.
# RATES_DB_URL=https://github.com/<owner>/spending-tracker/releases/download/rates-latest/exchange_rates.db
```

**After bootstrap**: the on-demand Frankfurter fetch in `ExchangeRateService` (Story 7.3) fills any gap between the artifact's cutoff date and today — at most ~24 h of missing rates on a healthy pipeline, a few days if the pipeline lagged.

**Air-gapped / offline users**: set `RATES_DB_URL` to a local file path or internal mirror URL. No runtime Frankfurter calls occur if all needed dates are already in the DB.

---

## Privacy Note

Frankfurter calls send only: a date, and two currency codes (e.g., `2024-03-15`, `from=USD`, `to=PHP`). No transaction amounts, descriptions, or user identifiers are transmitted. Rate data is not PII. Requests are outbound GET calls to `api.frankfurter.app`; there is no inbound data beyond the rate number.

Users who want zero external calls: run `POST /exchange-rates/prefetch` for all needed currency pairs and date ranges while online, then disconnect. All subsequent analytics use the local cache exclusively.

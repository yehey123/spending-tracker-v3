# Spending Tracker — Design Proposal

**Status**: ACCEPTED
**Date**: 2026-07-13
**Rationale**: Approved 2026-07-13 — build started on branch initial_backend.

---

## 1. Summary, Goals, Non-Goals

### Summary
Self-hosted personal finance app. Users upload credit card statement screenshots and bank statement PDFs; an OCR pipeline (OpenCV → configurable provider) extracts transactions; a Next.js PWA presents analytics. Distributable via browser install or App Store (Capacitor).

### Goals
- Automate transaction ingestion from statement files — no manual entry
- Clear visual breakdown of spending by category and time period
- Privacy-first: all processing local by default (Tesseract, no external API)
- Single self-hosted deployment; configurable backend URL from the app
- Mobile-first UI that installs from browser and ships via App Store (iOS, Android, iPad)

### Non-Goals
- No envelope/goal/budget tracking in v1
- No multi-user or authentication in v1 (auth is an explicit later pivot)
- No bank integration (Plaid, open banking) in v1
- No real-time push / transaction notifications in v1
- Not a receipt scanner (statement-level upload, not individual receipt photos)
- No end-to-end encryption of stored data in v1

---

## 2. Pros / Cons

### Pros
- Self-hosted → user controls all data, no SaaS privacy concerns
- Tesseract default → zero API keys required to get started
- Capacitor → single web codebase compiles to App Store + Play Store artifacts
- OpenCV preprocessing → meaningfully improves Tesseract accuracy on phone photos of statements
- Statement-based model → works with any bank without an API integration
- FastAPI async → suitable for file-upload / OCR workloads without blocking

### Cons
- Tesseract accuracy on compressed screenshots is variable; heavily skewed or low-res images will need manual correction
- Bank statement formats vary significantly — generic parser covers common patterns but will miss edge cases
- Capacitor has friction points vs. truly native (file picker UX, camera, push notifications)
- Self-hosting requires Docker knowledge; non-technical users are a harder install path
- No bank sync → user must manually upload statements periodically

---

## 3. Impact on Repo State

### Current state
Original NAFFL backend deleted (confirmed: `src/`, `tests/`, `requirements/`, `pyproject.toml`, `Dockerfile` removed). Partial backend scaffold created in `backend/` this session (models, OCR providers, DB session) — not yet wired. No frontend yet.

### New structure (full target)
```
spending-tracker/
├── design/                         ← this doc + contracts
├── backend/
│   ├── src/
│   │   ├── core/config.py          ← settings (db url, ocr provider, api keys)
│   │   ├── db/{base,session}.py    ← SQLAlchemy async engine + session dep
│   │   ├── domain/
│   │   │   ├── models/             ← Category, Statement, Transaction, AppSettings
│   │   │   └── services/
│   │   │       ├── ocr/            ← base + tesseract + claude + openai providers
│   │   │       ├── preprocessor.py ← OpenCV pipeline
│   │   │       ├── pdf_parser.py   ← pdfplumber extraction
│   │   │       └── statement_parser.py ← text → ParsedTransaction[]
│   │   ├── api/
│   │   │   ├── schemas/            ← Pydantic request/response models
│   │   │   └── routes/             ← transactions, statements, categories, settings, analytics
│   │   └── main.py                 ← FastAPI app, CORS, lifespan
│   ├── alembic/                    ← migrations
│   ├── tests/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── requirements/{base,dev}.{in,txt}
├── frontend/
│   ├── src/
│   │   ├── app/                    ← Next.js App Router pages
│   │   ├── components/
│   │   └── lib/{api.ts,types.ts}   ← API client (backend URL from localStorage)
│   ├── capacitor.config.ts
│   ├── next.config.ts
│   └── package.json
├── nginx/
│   └── nginx.conf                  ← reverse proxy: /api → backend, / → frontend
├── docker-compose.yml              ← Postgres + backend + frontend + nginx
└── Makefile
```

### Breaking changes
None — no consumers of the old code exist. Clean slate.

### Migrations
Alembic initial migration creates 4 tables: `categories`, `statements`, `transactions`, `app_settings`. No data to preserve.

### New dependencies

**Backend (Python)**

| Package | Purpose |
|---|---|
| `fastapi`, `uvicorn[standard]` | Web framework |
| `sqlalchemy[asyncio]`, `asyncpg` | Async ORM + Postgres driver |
| `alembic` | Schema migrations |
| `pydantic-settings` | Env-based config |
| `python-multipart` | File upload support |
| `pillow` | Image handling |
| `pytesseract` | Tesseract Python binding |
| `opencv-python-headless` | Image preprocessing (no GUI) |
| `pdfplumber` | PDF text/table extraction |
| `aiofiles` | Async file I/O |
| `anthropic` | Claude Vision (optional) |
| `openai` | GPT-4o Vision (optional) |

**Frontend (Node)**

| Package | Purpose |
|---|---|
| `next` | Framework |
| `react`, `react-dom` | UI runtime |
| `typescript` | Type safety |
| `@capacitor/core`, `@capacitor/ios`, `@capacitor/android`, `@capacitor/cli` | App Store packaging |
| `tailwindcss` | Styling |
| `recharts` | Analytics charts |
| `@tanstack/react-query` | Server state + caching |
| `react-dropzone` | File upload UX |
| `lucide-react` | Icons |

### Security notes
- OCR API keys stored in `app_settings` table in plaintext — acceptable for single-user self-hosted v1; flag for encryption if auth is added.
- `pickle` removed entirely from new backend (was in old code; not reintroduced).
- CORS configured to allow all origins by default (self-hosted; user controls the server). Can be tightened via env var.
- Uploaded files stored on local filesystem under a configurable `UPLOAD_DIR`. No path traversal risk as filenames are UUIDs, not user-supplied strings.

---

## 4. Alternatives Considered

### Alt A: Bank Integration (Plaid / open banking)
**Tradeoff**: Eliminates OCR entirely — accurate, real-time, no manual uploads. Rejected for v1 because: (a) Philippine banks have limited Plaid coverage, (b) data leaves the server to Plaid, contradicting the privacy-first goal, (c) significant API cost.

### Alt B: Manual transaction entry
**Tradeoff**: 100% accurate, trivial to build. Rejected — the core value proposition is eliminating manual entry.

### Alt C: Expo (React Native) instead of Next.js + Capacitor
**Tradeoff**: Better native feel (camera, haptics, push), but the user chose TypeScript / web patterns and prioritized build simplicity. Capacitor lets the same Next.js app run in the browser and submit to the App Store, requiring only one codebase and one language.

### Alt D: SQLite instead of PostgreSQL
**Tradeoff**: Zero-setup for self-hosting (no Postgres container). Viable for single-user. Rejected because async SQLite drivers (`aiosqlite`) are less battle-tested, and Postgres is already in the docker-compose. Can revisit if the install story becomes a pain point.

---

## 5. Risk Register

| ID | Risk | Class | Mitigation |
|---|---|---|---|
| R1 | Tesseract misreads low-quality statement screenshots | [ASSUMPTION] | OpenCV preprocessing (deskew, denoise, threshold) reduces this; provide manual correction UI |
| R2 | pdfplumber fails on image-based PDFs (scanned) | [ASSUMPTION] | Detect image-PDF and fall back to OCR pipeline for each page |
| R3 | Philippine bank statement formats not handled by generic parser | [UNKNOWN] | Parser is extensible; ship with generic patterns + allow user correction |
| R4 | App Store review rejects Capacitor build | [ASSUMPTION] | Add required privacy labels; test on TestFlight before submission |
| R5 | Auth retrofit is painful with single-user assumptions | [ASSUMPTION] | Add `user_id` FK placeholder to all tables now even if unused; soft-wires auth path |
| R6 | OCR API keys stored plaintext | KNOWN | Acceptable for v1 self-hosted; document the risk; prioritize encryption if auth lands |
| R7 | `opencv-python-headless` not available on Python 3.14 | [UNKNOWN] | Verify at implementation start; fallback to `opencv-python` or pin Python version |
| R8 | Frankfurter/ECB historical rates start 1999 — pre-1999 transactions have no automated source | KNOWN | Mark such transactions `unconverted` in analytics; never zero or silently skip. Future story: bundled IMF/World Bank CSV for older rates. |
| R9 | Frankfurter covers ~30 currencies (ECB basket + majors); exotic currencies absent | [ASSUMPTION] | Same unconverted-count path; user must manually seed missing pairs via a future manual-rate entry story |
| R10 | Frankfurter is an outbound external API call — contradicts "all processing local by default" goal | KNOWN | Rate data is not PII. Mitigated: the daily CI pipeline ships a pre-seeded `exchange_rates.db` artifact (Story 7.6); on first `docker compose up` the bootstrap downloads it so no live Frankfurter call is needed for historical data. On-demand fetch (Story 7.3) fills only the ~24 h gap since the last artifact publish. Air-gapped users override `RATES_DB_URL` to a local mirror. |
| R11 | Changing home currency retroactively recomputes all historical analytics | KNOWN | Expected behavior (convert-on-read); document clearly in Settings UI. No data loss — original amounts are always stored. |
| R12 | Analytics aggregation must join `exchange_rates` for every non-home transaction; degrades at scale | [ASSUMPTION] | Acceptable for single-user personal finance volumes (< 10k transactions). Index on `(date, base_currency, quote_currency)` covers the join. Revisit if needed. |

---

## 6. Epics → Stories → Scopes

---

### E1: Statement Ingestion

**Outcome**: User uploads a file and transactions appear automatically.

---

#### Story 1.1 — Upload credit card screenshot
> As a user, I want to upload a screenshot of my credit card statement, so that my transactions are automatically extracted and logged.

**Acceptance criteria**
- Given a PNG or JPEG is `POST`-ed to `/statements/upload`
- When the server runs OpenCV preprocessing → configured OCR provider
- Then transactions are parsed, saved to `transactions`, linked to the statement record
- And `statements.status` = `done` with `transaction_count` in the response
- And if parsing fails, `status` = `failed` with `error_message`

**In scope**: PNG, JPEG upload; OpenCV preprocess; Tesseract/Claude/OpenAI OCR; generic transaction line parser; DB persistence.
**Out of scope**: HEIC/RAW formats; real-time progress streaming; duplicate detection.

**Touched files**: `backend/src/domain/services/preprocessor.py`, `backend/src/domain/services/ocr/`, `backend/src/domain/services/statement_parser.py`, `backend/src/api/routes/statements.py`, `backend/src/domain/models/statement.py`, `backend/src/domain/models/transaction.py`.

**Contract delta**: `POST /statements/upload` — see `contracts/api.md §statements`.

---

#### Story 1.4 — Staged extraction pipeline, markdown intermediate, and flag infrastructure

> As a user, I want the system to store what it extracted at every stage, so that I can see exactly what went wrong when parsing fails and retry individual stages without re-uploading.

---

**Pipeline stages (sequential, each stores output before handing off):**

```
Upload
  │
  Stage 1 — OCR (Tesseract or docTR)
  │   output: statements.raw_ocr_text
  │   failure: status=ocr_failed → stop, notify user
  │
  Stage 2 — Parser → markdown table  [deterministic]
  │   output: statements.markdown_content
  │   partial: save parsed rows, record failures in statements.parse_errors JSONB
  │   total failure: status=parse_failed → stop, markdown stored for manual edit
  │
  Stage 3 — AI categorization  [async, optional, retryable]
  │   input: statements.markdown_content (not raw OCR text)
  │   output: category_id + confidence per transaction row
  │   high confidence (≥ threshold): auto-apply, no flag
  │   low confidence (< threshold): apply tentatively, open low_confidence_category flag
  │   very low / error: category=null, open low_confidence_category flag
  │   failure: status=pending_categorization → retryable via POST /statements/{id}/categorize
  │
  Stage 4 — Duplicate detection  [deterministic, always runs after Stage 2]
      input: newly inserted transactions
      output: suspected_duplicate flags (never auto-drops)
```

---

**`statements` table additions:**

```sql
raw_ocr_text              TEXT          -- Stage 1 output, always kept
markdown_content          TEXT          -- Stage 2 output, re-parseable without re-OCR
parse_errors              JSONB         -- [{"raw_line": "...", "reason": "..."}, ...]
categorization_confidence FLOAT         -- avg confidence from Stage 3, null if skipped

-- status enum expanded:
status  ENUM(
  pending,
  ocr_failed,
  parse_failed,
  pending_categorization,   -- Stage 2 done, Stage 3 queued or retrying
  done
)
```

---

**`transactions` table additions:**

```sql
transaction_origin  ENUM(uploaded, manual, receipt)  -- how this row was created
created_at          TIMESTAMP NOT NULL DEFAULT now()  -- DB row creation time
updated_at          TIMESTAMP NOT NULL DEFAULT now()  -- last mutation (category, currency, etc.)
```

`updated_at` is set via a SQLAlchemy `onupdate` trigger — no manual tracking required.

---

**`transaction_flags` table (new — flag infrastructure):**

```sql
transaction_flags
  id              SERIAL PK
  transaction_id  INT REFERENCES transactions(id) ON DELETE CASCADE
  flag_type       ENUM(
                    suspected_duplicate,
                    low_confidence_category,
                    parse_error,
                    unrecognized_account,
                    suspected_transfer
                  )
  status          ENUM(open, resolved, dismissed)  NOT NULL DEFAULT 'open'
  metadata        JSONB         -- type-specific payload (see below)
  created_at      TIMESTAMP NOT NULL DEFAULT now()
  resolved_at     TIMESTAMP
  resolved_by     ENUM(user, system)

INDEX (transaction_id, status)
INDEX (flag_type, status)        -- powers review-queue queries
```

**Metadata shapes per flag type:**
```jsonc
// suspected_duplicate
{ "peer_id": 42, "days_apart": 1, "amount": "350.00", "account_id": 1 }

// low_confidence_category
{ "suggested_category_id": 3, "confidence": 0.61, "model": "claude-haiku-4-5" }

// parse_error
{ "raw_line": "MOVE IT      IT   450", "reason": "amount_ambiguous" }

// unrecognized_account
{ "detected_last_four": "9012" }

// suspected_transfer
{ "peer_id": 87, "peer_account_id": 2, "days_apart": 2, "amount": "15000.00" }
```

**Flag lifecycle:**
```
open
  ├── user takes action    → resolved  (resolved_by=user,   resolved_at=now())
  ├── system auto-resolves → resolved  (resolved_by=system, resolved_at=now())
  └── user dismisses       → dismissed (resolved_by=user,   resolved_at=now())
```

A transaction is "clean" when `SELECT COUNT(*) FROM transaction_flags WHERE transaction_id=? AND status='open'` = 0. Both `resolved` and `dismissed` are terminal — they clear from the review queue. The distinction feeds data-quality analytics: high dismiss rate on `suspected_duplicate` signals the detection window is too wide.

---

**Confidence thresholds (configurable in `app_settings`):**

```sql
ai_category_confidence_auto    FLOAT  DEFAULT 0.85  -- auto-apply, no flag
ai_category_confidence_suggest FLOAT  DEFAULT 0.50  -- apply tentatively, open flag
                                                     -- below this: null category, open flag
```

---

**Retry endpoints:**

```
POST /statements/{id}/ocr          -- re-run Stage 1 + all downstream stages
POST /statements/{id}/parse        -- re-run Stage 2 from stored raw_ocr_text
POST /statements/{id}/categorize   -- re-run Stage 3 from stored markdown_content
```

User can also edit `markdown_content` directly via `PATCH /statements/{id}` and then `POST /statements/{id}/parse` to re-derive transactions from a corrected markdown table.

---

**Acceptance criteria**

- Given a PNG is uploaded
- When Stage 1 (OCR) succeeds, `raw_ocr_text` is persisted before Stage 2 begins
- When Stage 2 (parser) produces a partial result, transactions from parsed rows are saved, `parse_errors` records the failed rows, and status reflects the partial outcome
- When Stage 3 (AI) times out or errors, already-saved transactions are untouched, `status=pending_categorization`, and `POST /statements/{id}/categorize` retries only Stage 3
- When Stage 1 fails, `status=ocr_failed`, `raw_ocr_text` contains whatever partial text was recovered, and no transactions are saved
- All new transactions carry `transaction_origin`, `created_at`, `updated_at`
- Flags created by Stage 3 (low_confidence_category) and Stage 4 (suspected_duplicate) are rows in `transaction_flags` with `status=open`
- `GET /transactions?transaction_id={id}` includes an `open_flag_count` field
- `GET /flags?status=open` returns all open flags, filterable by `flag_type`

**In scope**: `raw_ocr_text`, `markdown_content`, `parse_errors`, expanded `status` enum on `statements`; `transaction_origin`, `created_at`, `updated_at` on `transactions`; new `transaction_flags` table; alembic migration; retry endpoints; `docTR` as optional enhanced OCR provider (opt-in via `app_settings.ocr_provider`).
**Out of scope**: Real-time stage progress streaming (WebSocket); markdown editor UI (manual edit via API only in v1); `docTR` model auto-download on first use (must be pre-installed in image).

**New optional dependency**: `python-doctr[torch]` (CPU-only, ~200 MB model) — gated behind `ocr_provider=doctr` in settings; not installed by default (would bloat the base image). Install instructions in README.

**Touched files**: `backend/src/domain/models/statement.py`, `backend/src/domain/models/transaction.py`, new `backend/src/domain/models/transaction_flag.py`, `backend/alembic/versions/`, `backend/src/api/routes/statements.py`, new `backend/src/api/routes/flags.py`, `backend/src/api/schemas/`, `backend/src/domain/services/statement_parser.py`, `backend/src/core/config.py`.

---

#### Story 2.5 — AI categorization with confidence flags

> As a user, I want the system to suggest a category for each transaction using AI, so that I spend less time manually assigning categories after every upload.

**Acceptance criteria**
- Given a statement reaches Stage 3 (AI categorization)
- When the configured AI provider (Claude/OpenAI, reusing the OCR provider key from Story 1.3) receives the `markdown_content` table as a single batched prompt
- Then it returns `[{row_index, category_name, confidence}]` for each transaction row
- Rows with `confidence ≥ ai_category_confidence_auto` (default 0.85): category auto-applied, `transaction_flags` row created with `status=resolved, resolved_by=system`
- Rows with `confidence` between thresholds: category applied tentatively, `transaction_flags` row with `flag_type=low_confidence_category, status=open`
- Rows below `ai_category_confidence_suggest` (default 0.50): `category_id=null`, flag open
- Category names from AI are fuzzy-matched against existing `categories` rows; unmatched names create a `parse_error` entry rather than silently failing
- `POST /statements/{id}/categorize` retries Stage 3 for all transactions on that statement where `category_id IS NULL` or flag is open — idempotent
- If AI provider is not configured (`anthropic_api_key` and `openai_api_key` both null): Stage 3 is skipped entirely, no flags created, `status=done` after Stage 2

**AI prompt contract (sent as system + user message):**
```
System: You are a personal finance categorizer. Given a markdown table of bank
        transactions, return a JSON array: [{row, category, confidence}].
        Categories available: {category_list}.
        confidence is 0.0–1.0. Never invent categories not in the list.

User:   | Date | Description | Amount | Direction |
        | Jun 1 | GRAB FOOD | 350.00 | debit |
        | Jun 2 | MOVE | 450.00 | debit |
        ...
```

**In scope**: Stage 3 pipeline integration; batched prompt per statement; confidence threshold application; flag creation; `POST /statements/{id}/categorize` retry; fuzzy category name matching.
**Out of scope**: Per-transaction AI call (always batched); custom prompt configuration; category auto-creation from AI suggestions.

**Touched files**: new `backend/src/domain/services/categorizer.py`, `backend/src/api/routes/statements.py`, `backend/src/api/routes/flags.py`.

---

#### Story 2.6 — Flag review queue

> As a user, I want a single place to review and resolve all flagged items, so that I can clean up my data without hunting through individual transactions.

**Acceptance criteria**
- Given I open the Review page
- When `GET /flags?status=open` is called
- Then flags are returned grouped by `flag_type`, each with enough context to act (transaction description, amount, date, peer transaction for duplicates/transfers, suggested category for low-confidence)
- I can resolve flags individually or bulk-resolve by type: "Accept all AI category suggestions" resolves every open `low_confidence_category` flag for the current statement
- Resolving a `suspected_duplicate` flag requires choosing: Keep both / Discard new / Replace old — the choice is recorded in `metadata` and the appropriate transaction is soft-deleted
- Resolving a `suspected_transfer` flag links both transactions via `transfer_peer_id`
- Dismissing any flag sets `status=dismissed`; transaction is unchanged
- A badge in the nav shows total `open` flag count, updating in real time via React Query polling (5 s interval)
- `GET /analytics/data-quality` returns flag aggregate stats: open count by type, dismiss rate by type, avg AI confidence, `false_positive_rate` per detector

**In scope**: `GET /flags` with `status`, `flag_type`, `statement_id` filters; individual and bulk resolution endpoints; `PATCH /flags/{id}` for resolution; nav badge; data quality analytics endpoint; Review page UI.
**Out of scope**: Email/push notifications for new flags; flag snooze; flag assignment to specific users (single-user v1).

**Touched files**: new `backend/src/api/routes/flags.py`, `backend/src/api/schemas/flags.py`, `backend/src/api/routes/analytics.py`, new `frontend/src/app/review/page.tsx`, `frontend/src/components/layout/Nav.tsx`.

---

#### Story 2.7 — Merchant category memory and auto re-categorization

> As a user, I want correcting one transaction's category to automatically fix all similar transactions, so that I don't have to reassign the same merchant repeatedly.

**How it works — three-layer lookup on every categorization request:**

```
for each transaction description:
  1. normalize("GRAB FOOD *9A2B PH") → "GRAB FOOD"
  2. lookup merchant_category_memory WHERE description_normalized = "GRAB FOOD"
       HIT source=user_correction  → apply, no flag (confidence=1.0)
       HIT source=ai_confirmed     → apply, no flag
       HIT source=ai_suggested     → apply tentatively, low_confidence flag
       MISS                        → add to AI batch (Story 2.5)
  3. AI result → store back to memory (source=ai_suggested) → apply per threshold
```

AI calls only fire on cache misses. First upload cold; subsequent uploads from the same institution are mostly cache hits.

**Normalization strips OCR noise before storing or matching:**
```python
def normalize(desc: str) -> str:
    desc = desc.upper()
    desc = re.sub(r'[*#]\w+', '', desc)      # strip reference codes: *9A2B
    desc = re.sub(r'\s+PH\s*$', '', desc)    # strip trailing location: " PH"
    desc = re.sub(r'\s{2,}', ' ', desc)      # collapse OCR whitespace gaps
    return desc.strip()
```

"GRAB FOOD \*9A2B PH" and "GRAB FOOD \*ZX91" → both → "GRAB FOOD" → same cache hit.

**`merchant_category_memory` table:**

```sql
merchant_category_memory
  description_normalized  VARCHAR(200)  PRIMARY KEY  -- normalized merchant name
  category_id             INT REFERENCES categories(id) ON DELETE SET NULL
  source                  ENUM(user_correction, ai_confirmed, ai_suggested)
  confidence              FLOAT         -- null for user_correction (implicit 1.0)
  usage_count             INT DEFAULT 1
  last_used_at            TIMESTAMP NOT NULL DEFAULT now()
  created_at              TIMESTAMP NOT NULL DEFAULT now()
```

**Source promotion rules:**
```
ai_suggested + user confirms same category  → promoted to ai_confirmed
ai_suggested + user assigns different cat   → overwritten as user_correction
user_correction                             → never demoted by AI
```

**Auto re-categorization trigger (fires on every `PATCH /transactions/{id}` category change):**

```
User assigns transaction "GRAB FOOD *9A2B" → Food Delivery
  → normalize → "GRAB FOOD"
  → UPSERT merchant_category_memory (source=user_correction, confidence=null)
  → SELECT transactions WHERE normalize(description) = "GRAB FOOD"
      AND (category_id != :new_id OR category_id IS NULL)
      AND transaction_origin != 'manual'   -- don't auto-change hand-entered rows
  → bulk UPDATE category_id
  → resolve open low_confidence_category flags on affected transactions (resolved_by=system)
  → return { "re_categorized": 12 }  in PATCH response
```

**Acceptance criteria**
- Given I reassign "GRAB FOOD \*9A2B" to "Food Delivery"
- When `PATCH /transactions/{id}` is called
- Then all other transactions whose normalized description matches "GRAB FOOD" are updated to the same category
- And their open `low_confidence_category` flags are resolved automatically
- And the response includes `re_categorized: N`
- Given the same merchant appears in a future upload
- When Stage 3 (categorization) runs
- Then the merchant memory returns the category without an AI call
- Given an AI result is stored (source=ai_suggested) and the user later confirms it via the review queue
- Then the memory entry is promoted to `ai_confirmed` and future hits skip the flag

**In scope**: `merchant_category_memory` table and migration; normalization function; lookup in Stage 3 before AI batch; UPSERT on user correction; bulk re-categorization on patch; source promotion on flag resolution; `re_categorized` field in PATCH response.
**Out of scope**: Fuzzy matching beyond exact normalized match (pg_trgm extension deferred to v2); cross-account merchant memory sharing; memory export/import.

**Touched files**: new `backend/src/domain/models/merchant_memory.py`, new `backend/src/domain/services/merchant_memory.py`, `backend/src/domain/services/categorizer.py`, `backend/src/api/routes/transactions.py`, `backend/src/api/routes/flags.py`, `backend/alembic/versions/`.

---

#### Story 2.8 — Transaction fuzzy search with cursor-based pagination

> As a user, I want to search my transactions by description and scroll through results, so that I can quickly find a specific entry to link a receipt to it (or just look something up).

**Why cursor-based, not offset:**
`OFFSET N` forces a full index scan of N rows on every page — O(N) cost that grows with depth. Keyset cursors (`WHERE (date, id) < (:d, :id)`) are always O(1) regardless of how deep the user scrolls.

**Scale ladder (same API contract, swappable backend):**

| Realistic row count | Backend | Index type |
|---|---|---|
| Up to ~10M (personal tracker) | PostgreSQL `pg_trgm` | `GIN (description gin_trgm_ops)` |
| 10M–100M | PG + monthly date-range partitions | same, per partition |
| 100M+ | Elasticsearch/OpenSearch fed by Postgres CDC | same contract |

**Index (applied in migration):**
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_transactions_description_trgm
  ON transactions USING GIN (description gin_trgm_ops);
```

**API contract:**

```
GET /transactions/search
  ?q=grab food          # fuzzy query; absent or empty → return all (ordered by date desc)
  &limit=100            # max 100; default 100
  &cursor=<token>       # absent on first page; opaque base64
  &linkable_only=true   # optional: exclude rows that already have children or a parent
                        # (for the receipt-linking picker)

Response 200:
{
  "data": [
    {
      "id": 7,
      "date": "2026-06-14",
      "description": "GRAB FOOD",
      "amount": "500.00",
      "direction": "debit",
      "category": { "id": 3, "name": "Food Delivery", "color": "#f97316" },
      "has_children": false,
      "parent_transaction_id": null
    }
  ],
  "next_cursor": "eyJkYXRlIjoiMjAyNi0wNi0xNCIsImlkIjo3fQ==",
  "has_next": true
}
```

Cursor encodes `{"date": "...", "id": N}` (base64 JSON). Backend decodes and applies:
```sql
WHERE (date, id) < (:cursor_date, :cursor_id)
```

**Fuzzy query:**
```sql
SELECT *, similarity(description, :q) AS score
FROM transactions
WHERE (:q IS NULL OR description % :q OR description ILIKE '%' || :q || '%')
  AND (:linkable_only IS FALSE
       OR (parent_transaction_id IS NULL AND NOT EXISTS (
             SELECT 1 FROM transactions c WHERE c.parent_transaction_id = transactions.id)))
  AND (:cursor IS NULL OR (date, id) < (:cursor_date, :cursor_id))
ORDER BY
  CASE WHEN :q IS NOT NULL THEN similarity(description, :q) END DESC,
  date DESC, id DESC
LIMIT :limit + 1   -- fetch one extra to determine has_next; drop it from response
```

Fetching `limit + 1` rows lets the backend set `has_next` without a separate COUNT query (which is O(N) on large tables).

**Frontend behaviour:**
- Search input → debounce 300 ms → `GET /transactions/search?q=<value>` (resets cursor)
- Scroll reaches bottom → `GET /transactions/search?q=<value>&cursor=<last_cursor>`
- `has_next: false` → stop fetching; no spinner
- Empty `q` → returns all transactions newest-first (full browse, same pagination)

**Receipt-linking picker flow:**
1. Flag review card for `receipt_unlinked` shows the receipt's OCR lines + total
2. Search box pre-populated with receipt merchant name (from Phase 2 parse)
3. `?linkable_only=true` filters out already-decomposed transactions
4. Top 5 suggestions from the upload response are pinned at the top of the first page
5. User scrolls / refines query → taps a row → `PATCH /transactions/{child_id}/parent`

**Acceptance criteria**
- Given I call `GET /transactions/search?q=grab` with 250 matching transactions
- When the first page returns 100 rows and `has_next: true`
- Then passing `cursor` from the response returns the next 100 with stable ordering (no row repeated, no row skipped)
- Given I call with `q=grb fd` (typo)
- Then results include "GRAB FOOD" entries (trigram similarity match)
- Given I call with `linkable_only=true`
- Then transactions that already have children or a `parent_transaction_id` are excluded
- Given the table has 1M rows
- Then response time is under 200 ms (GIN index, keyset cursor — no full scan)

**In scope**: `pg_trgm` extension + GIN index migration; `GET /transactions/search` endpoint; cursor encoding/decoding; `linkable_only` filter; frontend debounce + infinite scroll hook (`useTransactionSearch`).
**Out of scope**: Full-text ranking beyond trigram similarity; cross-field search (amount, date range — add as `&min_date=` params in a future story); Elasticsearch integration (deferred to 100M+ scale).

**Touched files**: new migration for `pg_trgm` index; `backend/src/api/routes/transactions.py`; new `frontend/src/hooks/useTransactionSearch.ts`; `frontend/src/app/review/page.tsx` (receipt-linking picker).

---

#### Story 2.9 — Receipts review dashboard

> As a user, I want a dedicated screen showing all my uploaded receipts so that I can decide — one by one — whether each is a standalone expense or a breakdown of a CC statement entry.

**Two explicit states (no ambiguous "pending"):**

| State | Meaning | Effect on totals |
|---|---|---|
| **Unlinked** | Receipt is its own set of expenses (cash, non-CC purchase, or user explicitly chose standalone) | Children are normal standalone transactions; nothing excluded |
| **Linked** | Receipt decomposes a CC statement line item | Parent CC transaction excluded from totals; children's amounts used instead |

The `receipt_unlinked` flag (created on upload) resolves the moment the user makes a deliberate choice either way — it is never a permanent state.

**API endpoints:**

```
GET /receipts
  ?status=unlinked|linked|all    # default: all
  &cursor=<token>                # keyset cursor, 50 per page
  
Response 200:
{
  "data": [
    {
      "statement_id": 3,
      "filename": "grab_receipt.jpg",
      "uploaded_at": "2026-07-18T10:00:00Z",
      "receipt_total": "500.00",
      "status": "linked",          # "linked" | "unlinked"
      "parent_transaction": {      # null when unlinked
        "id": 7,
        "date": "2026-06-14",
        "description": "GRAB FOOD",
        "amount": "500.00"
      },
      "children": [
        { "id": 101, "description": "Food",         "amount": "350.00", "category": {...} },
        { "id": 102, "description": "Delivery fee", "amount": "150.00", "category": {...} }
      ],
      "suggested_parents": [       # top 5 from upload-time soft match; empty if already linked
        { "id": 7,  "description": "GRAB FOOD", "date": "2026-06-14", "amount": "500.00" },
        { "id": 12, "description": "GRAB FOOD", "date": "2026-06-12", "amount": "500.00" }
      ]
    }
  ],
  "next_cursor": "eyJpZCI6M30=",
  "has_next": false
}


POST /receipts/{statement_id}/link
  body: { "parent_transaction_id": 7 }
  → validates: sum(children.amount) == parent.amount  (±0.01 rounding tolerance)
  → if mismatch: 422 { "code": "AMOUNT_MISMATCH", "receipt_total": "480.00", "parent_amount": "500.00", "difference": "20.00" }
  → sets parent_transaction_id on all children
  → resolves receipt_unlinked flag (resolved_by=user)
  → 200 { "linked_to": 7, "children_updated": 3 }

POST /receipts/{statement_id}/unlink
  → clears parent_transaction_id on all children (revert to standalone)
  → resolves receipt_unlinked flag (resolved_by=user, reason="standalone")
  → old parent transaction reverts to normal in totals
  → 200 { "children_updated": 3 }

POST /receipts/{statement_id}/reassign
  body: { "parent_transaction_id": 9 }
  → validates: sum(children.amount) == new_parent.amount  (same rule)
  → unlinks from old parent (old parent reverts to normal)
  → links to new parent
  → 200 { "linked_to": 9, "children_updated": 3 }
```

**Amount validation (enforced on link and reassign):**
```python
children_total = sum(c.amount for c in receipt.children)
if abs(children_total - new_parent.amount) > Decimal("0.01"):
    raise HTTPException(422, detail={
        "code": "AMOUNT_MISMATCH",
        "receipt_total": str(children_total),
        "parent_amount": str(new_parent.amount),
        "difference": str(abs(children_total - new_parent.amount)),
    })
```

Partial linking (receipt total ≠ parent amount) is always rejected. The user must either fix the children's amounts manually or choose a different parent.

**Frontend — receipts dashboard card:**

Each card shows:
- Receipt thumbnail / OCR text preview
- Extracted line items with their categories
- Receipt total
- Status badge: **Linked →** [parent description + date] | **Unlinked (own expense)**
- Suggested parents pinned at top (pre-populated from upload-time query)
- "Search for parent" button → opens Story 2.8 search picker with `linkable_only=true`
- Actions: Link | Unlink | Reassign (replaces Link when already linked)

**Acceptance criteria**
- Given I upload a Grab receipt with 3 line items totalling ₱500
- When I open the Receipts dashboard
- Then the receipt card shows status "Unlinked", all 3 children, and up to 5 suggested parents
- When I tap "Link" and select the "GRAB FOOD ₱500" suggestion
- Then `POST /receipts/{id}/link` links the children, resolves the `receipt_unlinked` flag, and the parent no longer appears in spending totals
- When I tap "Reassign" and pick a different parent with the same ₱500 amount
- Then the old parent reverts to normal in totals, the new parent is excluded
- When I try to reassign to a parent with amount ₱450 (different total)
- Then a 422 AMOUNT_MISMATCH error is shown with the difference ("₱50.00 gap")
- When I tap "Unlink"
- Then the children become standalone expenses, the parent reverts, and status shows "Unlinked (own expense)"

**In scope**: `GET /receipts`; `POST /receipts/{id}/link|unlink|reassign`; amount mismatch 422; receipts dashboard page; receipt card component; `receipt_unlinked` flag resolution; `suggested_parents` in GET response.
**Out of scope**: Editing receipt line item amounts from this screen (use `PATCH /transactions/{id}`); merging two receipts into one parent; splitting one receipt across multiple parents.

**Touched files**: `backend/src/api/routes/receipts.py` (new); `backend/src/api/schemas/receipts.py` (new); `frontend/src/app/receipts/page.tsx` (new); `frontend/src/components/receipts/ReceiptCard.tsx` (new); `frontend/src/hooks/useReceipts.ts` (new).

---

#### Story 1.5 — Receipt upload and transaction decomposition

> As a user, I want to upload a receipt alongside (or after) a CC statement, so that a single billed line item is broken down into its real sub-categories without double-counting my spending.

**The problem without this story**: uploading a ₱500 "GRAB FOOD" CC line item and a Grab receipt showing ₱350 food + ₱150 delivery creates ₱1 000 total spend in reports — double-counted.

**Schema addition:**

```sql
ALTER TABLE transactions
  ADD COLUMN parent_transaction_id INT REFERENCES transactions(id) ON DELETE SET NULL;
-- null = standalone (CC line item or manual)
-- non-null = this row is a receipt breakdown child of the parent
```

**Reporting rule**: when a transaction has at least one child, its amount is excluded from all aggregations; only the children's amounts are summed. Deleting all children reverts the parent to normal.

**File classification in the pipeline (runs after Stage 1 OCR):**

| Signal | Classification |
|---|---|
| Multi-page PDF or > 5 table rows | `statement` |
| Single-page image or single-page PDF with item list | `receipt` |
| Ambiguous | treated as `statement` (conservative) |

`statements.file_type ENUM(statement, receipt, unknown)` stored on ingest.

**Single-API-call batch — two-phase processing:**

```
POST /statements/upload   (multipart, multiple files allowed)

Phase 1 — all statement files:
  Stage 1 OCR → Stage 2 parse → Stage 3 categorize → Stage 4 duplicate detect
  → commit transactions (transaction_origin = 'uploaded')

Phase 2 — all receipt files (starts only after Phase 1 commits):
  Stage 1 OCR → Stage 2 parse → receipt-match against Phase 1 output
  → if match: set parent_transaction_id, origin = 'receipt'
  → if no match: store standalone, flag receipt_unmatched

Response:
{
  "statements": [{ "id": 1, "transactions_created": 12 }],
  "receipts": [
    { "id": 2, "matched_to": 7,  "children_created": 3 },
    { "id": 3, "matched_to": null, "children_created": 1, "flags": ["receipt_unmatched"] }
  ]
}
```

Phase 2 jobs carry a `depends_on: [phase1_job_id]` in the task queue so they never race the commit.

**Receipt-to-parent suggestion (soft, never auto-links):**

After Phase 2 OCR+parse, the backend runs a single candidate query:

```sql
SELECT id, description, amount, date
FROM transactions
WHERE ABS(amount - :receipt_total) / NULLIF(:receipt_total, 0) < 0.05
  AND ABS(date - :receipt_date) <= 5
  AND parent_transaction_id IS NULL
  AND transaction_origin = 'uploaded'
ORDER BY ABS(date - :receipt_date) ASC, ABS(amount - :receipt_total) ASC
LIMIT 5
```

The top suggestion is returned in the upload response. The receipt is **never silently linked** — the user always confirms via the search-and-link UI (Story 2.8). This sidesteps all false-positive matching problems: tip variance, FX rounding, settlement date lag, two same-amount transactions on the same day.

**New flag type (added to existing ENUM):**
- `receipt_unlinked` — receipt uploaded, children created, awaiting user to pick a parent via search UI

**Link/unlink endpoint:**

```
PATCH /transactions/{child_id}/parent
  body: { "parent_transaction_id": 7 }   -- link: excludes parent from totals
  body: { "parent_transaction_id": null } -- unlink: both revert to standalone
```

**Acceptance criteria**
- Given I POST a CC statement PDF and a Grab receipt image in one multipart call
- When Phase 1 commits the "GRAB FOOD ₱500" transaction
- Then Phase 2 creates receipt child rows with flag `receipt_unlinked` and returns top 5 suggested parents
- When I confirm a suggestion (or search and pick manually via Story 2.8)
- Then `PATCH /transactions/{child_id}/parent` links them, parent is excluded from totals, children's amounts are used instead
- Given I delete all children of a parent
- Then the parent reverts to appearing normally in totals

**In scope**: `parent_transaction_id` migration; `file_type` on statements; two-phase batch ordering; soft suggestion query; `receipt_unlinked` flag; link/unlink endpoint; reporting exclusion rule.
**Out of scope**: Silent auto-linking (never); receipt OCR quality improvements.

**Touched files**: new migration `backend/alembic/versions/`, `backend/src/domain/models/statement.py`, `backend/src/domain/models/transaction.py`, `backend/src/api/routes/statements.py`, `backend/src/api/routes/transactions.py`, `backend/src/api/schemas/transactions.py`.

---

#### Story 1.6 — Pre-commit review screen and upload mode setting

> As a user, I want to choose whether to review extracted transactions before they enter my ledger, so that I can catch OCR errors before they affect my spending reports.

**Upload mode setting (stored in `app_settings`):**

```
review_before_commit  BOOLEAN  DEFAULT true
```

| Mode | Behaviour |
|---|---|
| `true` (default) | Pipeline pauses at `staged`; user must commit explicitly |
| `false` | Pipeline auto-commits after Stage 4; flag queue handles corrections |

Same pipeline, same stages. The only difference is whether `statements.status` waits at `staged` or skips to `committed`.

**`statements.status` state machine (updated):**

```
processing
  → staged        (review_before_commit = true)
      → committed (user approves)
      → discarded (user cancels)
      → expired   (TTL: 7 days, background job)
  → committed     (review_before_commit = false, auto after Stage 4)
  → error         (pipeline failure at any stage)
```

**Staged transactions:**
- Visible only in the review screen, not in the main transaction list or analytics
- Every inline edit fires `PATCH /staged-transactions/{id}` immediately — no "save draft" button; corrections persist across sessions and devices
- `declared_total` field on `statements`: OCR attempts to extract the statement's printed total; used as a reconciliation check header in the review screen

**Review screen layout:**

```
┌─────────────────────────────┬──────────────────────────────────────────┐
│  [Statement image / PDF]    │  BPI CC Statement — June 2026            │
│                             │  Extracted ₱15,432.50  ·  47 rows        │
│  < page 1 of 3 >            │  Declared  ₱15,432.50  ✅ totals match   │
│                             │  ────────────────────────────────────────│
│                             │  ⚠ Jun 14  GRAB FOOD       ₱1,50  [edit]│
│                             │    Jun 13  SM SUPERMARKET  ₱892.00       │
│                             │    Jun 12  MERALCO         ₱3,200.00     │
│                             │    ...                                    │
│                             │  ────────────────────────────────────────│
│                             │  [Discard]        [Commit 47 transactions]│
└─────────────────────────────┴──────────────────────────────────────────┘
```

- Flagged rows (OCR low confidence, amount looks like a misread, AI category uncertain) highlighted in amber
- Unflagged rows shown normally — quick visual scan is enough for most uploads
- "Commit" button is disabled until declared total matches extracted total (or user explicitly overrides the mismatch warning)
- Total mismatch shows: `⚠ ₱120.00 gap — check highlighted rows before committing`

**Endpoints:**

```
GET  /statements/{id}/staged          → list of staged transactions for review
PATCH /staged-transactions/{id}       → inline edit (amount, description, category, direction)
POST /statements/{id}/commit          → promote all staged → active; statement → committed
POST /statements/{id}/discard         → delete all staged rows; statement → discarded
```

**TTL cleanup (background job, runs nightly):**
```sql
UPDATE statements SET status = 'expired'
WHERE status = 'staged'
  AND updated_at < NOW() - INTERVAL '7 days';

DELETE FROM transactions
WHERE status = 'staged'
  AND statement_id IN (SELECT id FROM statements WHERE status = 'expired');
```

**Acceptance criteria**
- Given `review_before_commit = true` and I upload a statement
- When the pipeline completes Stage 4
- Then `statements.status` = `staged` and no transactions appear in the main list
- When I edit an amount inline and navigate away
- Then the correction persists when I return (saved to backend immediately)
- When declared total matches extracted total and I click "Commit"
- Then all staged transactions become active and appear in the main list and analytics
- Given `review_before_commit = false` and I upload a statement
- When the pipeline completes Stage 4
- Then transactions are immediately active with no review step
- Given a staged statement not committed within 7 days
- Then its staged transactions are deleted and status becomes `expired`

**In scope**: `review_before_commit` setting; `staged` / `committed` / `discarded` / `expired` status transitions; `GET /statements/{id}/staged`; `PATCH /staged-transactions/{id}`; `POST /statements/{id}/commit|discard`; TTL cleanup job; review screen with side-by-side image; declared total reconciliation header.
**Out of scope**: Partial commit (commit some rows, leave others staged); concurrent multi-user review locking (v1 is single-user).

**Touched files**: `backend/src/api/routes/statements.py`; new `backend/src/api/routes/staged_transactions.py`; `backend/src/domain/models/statement.py`; `backend/src/tasks/ttl_cleanup.py` (new); new `frontend/src/app/statements/[id]/review/page.tsx`; `frontend/src/components/statements/StagedTransactionRow.tsx` (new).

---

#### Story 1.2 — Upload bank statement PDF
> As a user, I want to upload a PDF bank statement, so that my inflows and outflows are automatically captured.

**Acceptance criteria**
- Given a PDF is `POST`-ed to `/statements/upload`
- When pdfplumber extracts text/tables from each page
- Then transactions are parsed with `direction` (debit/credit) from the text
- And `statements.status` = `done` with transaction count
- If the PDF is image-based, the pipeline falls back to OCR per page

**In scope**: PDF upload; pdfplumber text extraction; image-PDF fallback to OCR; generic bank statement parser.
**Out of scope**: Password-protected PDFs (v1 rejects with 400).

**Touched files**: `backend/src/domain/services/pdf_parser.py`, `backend/src/domain/services/statement_parser.py`, `backend/src/api/routes/statements.py`.

---

#### Story 1.3 — Configure OCR provider
> As a user, I want to choose which OCR backend processes my images, so that I can balance privacy vs. accuracy.

**Acceptance criteria**
- Given the Settings screen shows provider options: Tesseract | Claude Vision | OpenAI Vision
- When I select Claude Vision and enter my API key and tap Save
- Then `PUT /settings` persists the selection to `app_settings`
- And future screenshot uploads use Claude Vision
- And the API key field shows only `••••` after save (key not returned in `GET /settings`)

**In scope**: Provider selection; API key storage in `app_settings`; key masking in GET response.
**Out of scope**: Key rotation; per-upload provider override.

**Touched files**: `backend/src/domain/models/app_settings.py`, `backend/src/api/routes/settings.py`, `backend/src/api/schemas/settings.py`.

---

### E2: Transaction Management

**Outcome**: User can review, correct, and curate the extracted transaction list.

---

#### Story 2.1 — View transactions list
> As a user, I want to see all my transactions in a list, so that I can review what was captured.

**Acceptance criteria**
- Given the Transactions page loads
- When `GET /transactions` is called (with optional `?month=YYYY-MM` filter)
- Then a paginated list is returned, sorted by date descending
- Each row shows: date, description, amount, direction (debit/credit), category name + color

**In scope**: Pagination (`limit`/`offset`); date filter; category join.
**Out of scope**: Full-text search (v1), export.

**Touched files**: `backend/src/api/routes/transactions.py`, `frontend/src/app/transactions/page.tsx`.

---

#### Story 2.2 — Edit transaction

> As a user, I want to correct a transaction's fields, so that my ledger is accurate without losing the original record.

**Two mutation classes — different rules:**

| Field | Committed transaction | Staged transaction |
|---|---|---|
| `amount`, `date`, `direction`, `description` | Reverse + Create (ledger immutability) | Direct `UPDATE` — not in ledger yet |
| `category_id` | Direct `UPDATE` + `audit_log` row | Direct `UPDATE` |

**Financial field correction on a committed transaction (PATCH = reverse + create):**

`PATCH /transactions/{id}` with any financial field change atomically:
1. Creates a reversal row (`reversal_of = original.id`, `reversal_reason = "user_correction"`)
2. Creates a correction row with the new values (`correction_of = original.id`)
3. Sets `reversed_by` and `corrected_by` on the original

```
original (id=7):    GRAB FOOD  ₱500  debit  Jun 14  reversed_by=8  corrected_by=9
reversal (id=8):    GRAB FOOD  ₱500  credit Jun 14  reversal_of=7  reason="user_correction"
correction (id=9):  GRAB FOOD  ₱350  debit  Jun 14  correction_of=7
```

Analytics exclude id=7 (`reversed_by` set) and id=8 (`reversal_of` set). Only id=9 counts.

**Schema addition:**
```sql
ALTER TABLE transactions
  ADD COLUMN correction_of  INT REFERENCES transactions(id),
  ADD COLUMN corrected_by   INT REFERENCES transactions(id);
```

**Category change on a committed transaction (direct update + audit log):**

Category is classification metadata, not a financial fact. Direct update avoids flooding the ledger with reversal pairs on every merchant memory bulk re-categorization (Story 2.7).

```sql
CREATE TABLE audit_log (
  id              SERIAL PRIMARY KEY,
  transaction_id  INT          NOT NULL REFERENCES transactions(id),
  field           VARCHAR(50)  NOT NULL,   -- 'category_id'
  old_value       TEXT,
  new_value       TEXT,
  changed_at      TIMESTAMP    NOT NULL DEFAULT now(),
  changed_by      VARCHAR(20)  NOT NULL,   -- 'user' | 'system'
  reason          TEXT
);
```

Every `PATCH category_id` on a committed transaction appends one `audit_log` row before updating the field. `GET /transactions/{id}/history` returns the full log for that transaction.

**Staged transaction edits (`PATCH /staged-transactions/{id}`):**
All fields — plain `UPDATE`. No reversal, no audit log. Staged rows are pre-ledger; they exist in the backend DB (accessible from any client) but have not become permanent entries yet.

**Acceptance criteria**
- Given a committed transaction with amount ₱500
- When I `PATCH /transactions/{id}` with `{ "amount": 350 }`
- Then the original is untouched but gains `reversed_by` and `corrected_by`
- And a reversal row and a correction row are created atomically
- And only the correction row appears in the transaction list and analytics
- Given a committed transaction with category "Uncategorized"
- When I `PATCH /transactions/{id}` with `{ "category_id": 3 }`
- Then `category_id` is updated directly and an `audit_log` row records the old and new value
- Given a staged transaction
- When I `PATCH /staged-transactions/{id}` with any field
- Then the row is updated directly with no reversal or audit log

**In scope**: Financial field reversal+create; `correction_of` / `corrected_by` columns; `audit_log` table and migration; `GET /transactions/{id}/history`; staged transaction direct update; analytics exclusion of reversed/reversal rows.
**Out of scope**: Bulk financial correction; correcting a correction (create a new correction_of the correction row instead).

**Touched files**: new migration `backend/alembic/versions/`; `backend/src/api/routes/transactions.py`; new `backend/src/api/routes/staged_transactions.py`; new `backend/src/domain/models/audit_log.py`; `frontend/src/app/transactions/page.tsx`.

---

#### Story 2.3 — Reverse transaction

> As a user, I want to reverse a transaction with a reason, so that errors and duplicates are corrected without destroying the audit trail.

**Why reversal, not deletion**: committed transactions are permanent ledger entries. Deleting them breaks the audit trail and makes disputes irrecoverable. A reversal posts an equal-and-opposite entry, nets to zero, and preserves the full history.

**Schema additions (all four columns land together in one migration with Story 2.2):**
```sql
ALTER TABLE transactions
  ADD COLUMN reversal_of     INT  REFERENCES transactions(id),
  ADD COLUMN reversal_reason VARCHAR(200),
  ADD COLUMN reversed_by     INT  REFERENCES transactions(id),
  ADD COLUMN correction_of   INT  REFERENCES transactions(id),
  ADD COLUMN corrected_by    INT  REFERENCES transactions(id);
```

**Pure reversal** (no replacement — used for duplicates, bank reversals, user errors):
```
original:  GRAB FOOD  ₱500.00  debit   Jun 14  reversed_by=8
reversal:  GRAB FOOD  ₱500.00  credit  Jun 14  reversal_of=7  reason="duplicate"
```
Net effect: ₱0. Both rows visible in audit ledger, neither counted in analytics.

**Correction** (reversal + replacement together — used for wrong amount/date/direction, see Story 2.2):
```
original (7):    GRAB FOOD  ₱500  debit  Jun 14  reversed_by=8  corrected_by=9
reversal (8):    GRAB FOOD  ₱500  credit Jun 14  reversal_of=7  reason="user_correction"
correction (9):  GRAB FOOD  ₱350  debit  Jun 14  correction_of=7
```

**API:**
```
POST /transactions/{id}/reverse
  body: {
    "reason": "duplicate",     -- ENUM: duplicate | bank_reversal | user_error
                               --       receipt_superseded | other
    "notes": "uploaded twice"  -- optional free text
  }

Response 200:
{
  "reversal_id": 8,
  "original_id": 7,
  "reason": "duplicate",
  "net_effect": "0.00"
}
```

409 Conflict if `reversed_by` is already set on the original.

**Reversal reasons:**
```
duplicate           — same transaction uploaded twice
bank_reversal       — the bank itself reversed the charge
user_error          — manually entered by mistake
receipt_superseded  — CC line item replaced by receipt breakdown (Story 1.5)
user_correction     — financial field corrected (set automatically by Story 2.2 PATCH)
other               — free text via notes field
```

**Analytics exclusion rule (single WHERE clause used everywhere):**
```sql
WHERE reversed_by  IS NULL    -- exclude originals that were reversed
  AND reversal_of  IS NULL    -- exclude the reversal rows themselves
  AND status != 'staged'      -- exclude pre-commit rows
```
Correction rows (`correction_of IS NOT NULL`) are included — they are the authoritative replacement.

**Acceptance criteria**
- Given a committed transaction
- When I tap "Reverse" and select reason "duplicate"
- Then `POST /transactions/{id}/reverse` creates a credit row with `reversal_of = original.id`
- And the original gains `reversed_by`; both are excluded from totals; both visible in ledger with "Reversed" badge
- Given I try to reverse an already-reversed transaction
- Then the API returns 409 Conflict
- Given a correction was applied (Story 2.2 PATCH on financial fields)
- Then the correction row IS included in analytics; the original and its reversal are not

**In scope**: All five FK columns migration (shared with Story 2.2); `POST /transactions/{id}/reverse`; 409 guard; analytics exclusion clause; "Reversed" badge.
**Out of scope**: Hard delete — never on committed transactions; bulk reversal; undoing a reversal (post a new forward entry instead).

**Touched files**: new migration `backend/alembic/versions/`; `backend/src/api/routes/transactions.py`; `backend/src/api/schemas/transactions.py`; `frontend/src/app/transactions/page.tsx`.

---

#### Story 2.4 — Manual transaction entry
> As a user, I want to add a transaction manually, so that I can log cash purchases not on any statement.

**Acceptance criteria**
- Given I tap "Add transaction" on the Transactions page
- When I fill in date, description, amount, direction, category and submit
- Then `POST /transactions` creates the record with `statement_id = null`

**In scope**: Manual entry form with all required fields.
**Out of scope**: Recurring transaction templates.

**Touched files**: `backend/src/api/routes/transactions.py`, `frontend/src/app/transactions/page.tsx`.

---

### E3: Spending Analytics

**Outcome**: User sees a clear picture of where their money goes.

---

#### Story 3.1 — Category spending breakdown
> As a user, I want to see my spending by category as a chart, so that I know where my money goes.

**Acceptance criteria**
- Given I open the Dashboard
- When `GET /analytics/by-category?month=YYYY-MM` returns data
- Then a donut chart shows debit spending grouped by category for the selected month
- Uncategorized transactions appear as "Uncategorized"

**In scope**: Donut chart; month picker; debit-only (spending, not inflows).
**Out of scope**: Year-to-date rollup (v1), custom date ranges.

**Touched files**: `backend/src/api/routes/analytics.py`, `frontend/src/app/dashboard/page.tsx`, `frontend/src/components/charts/SpendingDonut.tsx`.

---

#### Story 3.2 — Monthly cash flow
> As a user, I want to see total inflows vs. outflows per month, so that I understand my net position.

**Acceptance criteria**
- Given I view the Dashboard cash flow section
- When `GET /analytics/cash-flow?months=6` returns data
- Then a grouped bar chart shows credit (inflow) and debit (outflow) totals for each of the last N months
- Net (credit − debit) is shown as a number per month

**In scope**: Last 6 months bar chart; net calculation.
**Out of scope**: Forecasting, savings rate.

**Touched files**: `backend/src/api/routes/analytics.py`, `frontend/src/components/charts/CashFlowBar.tsx`.

---

### E4: App Shell & Configuration

**Outcome**: The app installs and connects to a user-specified backend.

---

#### Story 4.1 — Configurable backend URL
> As a self-hosting user, I want to set the backend address in the app, so that it talks to my own server.

**Acceptance criteria**
- Given I open the Settings page
- When I enter a URL and tap Save
- Then it is stored in `localStorage` under key `spending_tracker_backend_url`
- And all API calls in `lib/api.ts` use that URL from that point
- And a connection test pings `GET /health` and shows a success/failure indicator

**In scope**: URL input + validation; localStorage persistence; health-check ping.
**Out of scope**: Per-session URL override; VPN/tunnel setup guidance.

**Touched files**: `frontend/src/app/settings/page.tsx`, `frontend/src/lib/api.ts`.

---

#### Story 4.2 — PWA installability
> As a browser user, I want to install the app, so that it feels like a native app.

**Acceptance criteria**
- Given the Next.js app is deployed
- When a user visits in Chrome/Safari
- Then the app has a valid Web App Manifest and service worker
- And it can be added to the home screen and launches in standalone mode (no browser chrome)

**In scope**: `next-pwa` or `@ducanh2912/next-pwa` config; manifest with icons; offline shell.
**Out of scope**: Full offline mode with data sync.

**Touched files**: `frontend/next.config.ts`, `frontend/public/manifest.json`, `frontend/public/icons/`.

---

#### Story 4.3 — App Store packaging (Capacitor)
> As a mobile user, I want to install from the App Store, so that I get a native app experience.

**Acceptance criteria**
- Given Capacitor is configured with iOS and Android targets
- When `npx cap sync && npx cap build ios` runs
- Then a valid Xcode project is generated that can be archived and submitted to App Store Connect
- Same for Android (`npx cap build android` → valid Gradle project)

**In scope**: Capacitor config, iOS + Android targets, build Makefile targets.
**Out of scope**: CI/CD pipeline, code signing automation, push notifications.

**Touched files**: `frontend/capacitor.config.ts`, `frontend/package.json`, `Makefile`.

---

### E5: Category Management

**Outcome**: User controls how transactions are grouped.

---

#### Story 5.1 — Manage categories with two-level hierarchy
> As a user, I want to create parent categories and subcategories, rename, recolor, and delete them, so that my spending breakdown reflects how I actually think about money.

**Two levels only — no deeper.** Parent categories (Food & Dining, Transport) contain subcategories (Food Delivery, Ride Hailing). Transactions can be assigned to either level. Analytics roll up: a parent total includes all its children.

**Schema changes:**

```sql
categories
  parent_id   INT REFERENCES categories(id) NULLABLE  -- null = top-level parent
  slug        VARCHAR(50) UNIQUE NULLABLE              -- stable ID for system defaults
  is_system   BOOLEAN NOT NULL DEFAULT false           -- protects defaults from accidental delete
```

**Startup seeding (not a migration — runs in `lifespan()` before `yield`):**

```python
DEFAULTS = [
  # (slug, name, color, children)
  ("food",          "Food & Dining",    "#f97316", [
      ("food_delivery",  "Food Delivery",   "#fb923c"),
      ("fast_food",      "Fast Food",       "#fbbf24"),
      ("coffee",         "Coffee & Drinks", "#92400e"),
      ("groceries",      "Groceries",       "#84cc16"),
  ]),
  ("transport",     "Transport",        "#3b82f6", [
      ("ride_hailing",   "Ride Hailing",    "#60a5fa"),
      ("fuel",           "Fuel",            "#1d4ed8"),
      ("parking",        "Parking",         "#93c5fd"),
  ]),
  ("entertainment", "Entertainment",    "#a855f7", [
      ("streaming",      "Streaming",       "#c084fc"),
      ("events",         "Events",          "#7c3aed"),
  ]),
  ("bills",         "Bills & Utilities","#14b8a6", [
      ("internet",       "Internet",        "#2dd4bf"),
      ("mobile",         "Mobile",          "#0d9488"),
      ("electricity",    "Electricity",     "#f59e0b"),
  ]),
  ("income",        "Income",           "#22c55e", [
      ("salary",         "Salary",          "#16a34a"),
      ("freelance",      "Freelance",       "#4ade80"),
  ]),
  ("shopping",      "Shopping",         "#ec4899", [
      ("online",         "Online Shopping", "#f472b6"),
      ("clothing",       "Clothing",        "#db2777"),
  ]),
  ("health",        "Health",           "#06b6d4", [
      ("pharmacy",       "Pharmacy",        "#22d3ee"),
      ("medical",        "Medical",         "#0891b2"),
  ]),
]
```

Seeding uses `INSERT ... ON CONFLICT (slug) DO NOTHING` — idempotent on every restart. Adding new defaults to this list and deploying is the only operation required; no migration, no maintenance window. User-renamed or user-deleted system categories are not overwritten (insert skips on conflict; deleted rows have no slug to conflict on and will be re-seeded — acceptable for v1).

**Acceptance criteria**
- Given the Categories screen
- When I create a parent category with name and color, `POST /categories` persists it with `parent_id=null`
- When I create a subcategory under a parent, `POST /categories` persists it with `parent_id` set
- A subcategory cannot itself have children (enforced at API level: 422 if `parent_id` points to a row that already has a `parent_id`)
- `GET /categories` returns the full tree: `[{id, name, color, slug, is_system, children: [...]}]`
- When I delete a parent that has subcategories, the API returns 422: "Delete or reassign subcategories first"
- When I delete a category that has transactions, those transactions' `category_id` is set to null (Uncategorized)
- `is_system=true` categories show a warning before deletion but are not blocked
- The transaction category picker shows a two-level grouped select: parent optgroup → subcategory options; parent itself is also selectable
- Analytics `GET /analytics/by-category` groups by parent; subcategory breakdown is available via `?breakdown=subcategory`

**In scope**: `parent_id`, `slug`, `is_system` fields; alembic migration for new columns; startup seed in `lifespan()`; CRUD with hierarchy validation; two-level category picker UI; cascade-null on delete.
**Out of scope**: Category icons (field reserved, UI deferred); moving a subcategory between parents (v1: delete and recreate); more than two levels.

**Touched files**: `backend/src/domain/models/category.py`, `backend/src/api/routes/categories.py`, `backend/src/api/schemas/categories.py`, `backend/src/main.py` (seed in lifespan), `backend/alembic/versions/`, `frontend/src/app/settings/page.tsx`, `frontend/src/app/transactions/page.tsx` (grouped picker).

---

### E6: Deployment Gateway

**Outcome**: The full stack — frontend, backend, and database — runs behind a single nginx reverse proxy, reachable on one port with no manual URL configuration.

---

#### Story 6.1 — Frontend Docker service
> As a developer, I want the Next.js app to run in a container, so that the full stack is reproducible with a single command.

**Acceptance criteria**
- Given `frontend/Dockerfile` exists
- When `docker compose build` runs
- Then the image builds the Next.js app (`npm run build`) and serves it via `npm start` on port 3000
- And the image is included in `docker-compose.yml` as a `frontend` service depending on `backend`

**In scope**: Multi-stage Dockerfile (deps → build → runtime) on Node 24 (latest LTS); `NEXT_PUBLIC_API_URL` build arg; docker-compose `frontend` service.
**Out of scope**: CDN / static export; edge runtime.

**Touched files**: `frontend/Dockerfile`, `docker-compose.yml`.

---

#### Story 6.2 — nginx reverse-proxy gateway
> As a self-hosting user, I want a single URL to access the app, so that I don't have to manage separate ports for frontend and backend.

**Acceptance criteria**
- Given `NGINX_PORT` is set in the active `.env.compose.*` file (default `80`)
- When `docker compose` starts, the `nginx` service binds `${NGINX_PORT}:80`
- When a request arrives at `/api/` it is proxied to `backend:8000`, stripping the `/api` prefix
- When any other request arrives it is proxied to `frontend:3000`
- And `GET http://localhost:${NGINX_PORT}/health` returns the backend health response
- And `GET http://localhost:${NGINX_PORT}/` returns the Next.js homepage

**In scope**: `nginx/nginx.conf`; upstream blocks for `backend` and `frontend`; WebSocket upgrade headers for Next.js HMR (dev only, documented); docker-compose `nginx` service with `depends_on: [frontend, backend]`; `NGINX_PORT` in all `.env.compose.*` files with default `80`.
**Out of scope**: TLS termination (v1 HTTP only; document that a reverse proxy with cert is the production path); rate limiting; auth headers.

**Touched files**: `nginx/nginx.conf`, `docker-compose.yml`, `Makefile`.

---

#### Story 6.3 — Frontend API client wired to gateway
> As a developer, I want the frontend to call the backend through the nginx gateway by default, so that CORS is not an issue and no manual URL setup is required.

**Acceptance criteria**
- Given `NEXT_PUBLIC_API_URL` is set to `/api` in the production docker-compose environment
- When `lib/api.ts` constructs any request URL
- Then it uses `NEXT_PUBLIC_API_URL` as the base, falling back to the `localStorage` value from Story 4.1 if set (preserving direct-access dev mode)
- And `GET /api/health` from the browser returns `200` (same-origin, no CORS needed)

**In scope**: `lib/api.ts` base-URL resolution; `NEXT_PUBLIC_API_URL` env var in docker-compose; coexistence with Story 4.1 configurable URL (localStorage override wins for dev/direct-access).
**Out of scope**: Service worker fetch interception; auth headers.

**Relationship to E4 Story 4.1**: E4 Story 4.1's configurable URL remains valid for direct backend access (dev, mobile Capacitor builds). Behind nginx, `NEXT_PUBLIC_API_URL=/api` is the default and the localStorage override becomes an escape hatch, not the primary path.

**Touched files**: `frontend/src/lib/api.ts`, `docker-compose.yml`.

---

### E7: Multi-Currency Support

**Outcome**: User configures a home currency; all analytics aggregate into it at historical rates, regardless of the original currency on each transaction.

**Central architectural decision — convert-on-read at transaction-date rate**: Home-currency equivalents are never stored (they would go stale if the user later changes their home currency). Every analytics query converts amounts on the fly using the rate in effect on each transaction's date. Consequence: if the user changes home currency, all historical charts immediately update — this is correct behavior, not a bug. FX drift between the transaction date and today is not reflected; only the original rate matters.

**Rate-unavailable rule**: When no rate exists for a (date, currency pair), the transaction is counted in `unconverted_count` in the analytics response. It is **never** zeroed, silently excluded, or assumed to be 1:1.

---

#### Story 7.1 — Configure home currency
> As a user, I want to select my home (display) currency in Settings, so that all spending totals are shown in a currency I understand.

**Acceptance criteria**
- Given I open the Settings page
- When I select a currency from an ISO 4217 picker (populated from `GET /exchange-rates/supported`)
- Then `PUT /settings` persists `home_currency` (e.g. `"PHP"`) to `app_settings`
- And `GET /settings` returns `home_currency: "PHP"` (or `null` if not yet set)
- And when `home_currency` is null, the analytics page shows a prompt ("Set your home currency to see converted totals") rather than showing mixed-currency sums
- And changing the setting takes effect on the next analytics page load — no re-upload required

**In scope**: Currency picker (select element, sorted by ISO code, common currencies first) on Settings page; `home_currency VARCHAR(3) NULL` column on `app_settings`; alembic migration; updated `GET`/`PUT /settings` contract.
**Out of scope**: Per-account or per-statement currency; multiple home currencies; live FX ticker.

**Touched files**: `backend/src/domain/models/app_settings.py`, `backend/src/api/routes/settings.py`, `backend/src/api/schemas/settings.py`, `frontend/src/app/settings/page.tsx`, `frontend/src/lib/types.ts`, `backend/alembic/versions/`.

**Contract delta**: see `contracts/currency.md §settings`.

---

#### Story 7.2 — Tag transactions with original currency
> As a user, I want each transaction to carry the currency it was originally denominated in, so that the conversion system knows what to convert from.

**Acceptance criteria**
- Given a transaction record exists
- When viewed via `GET /transactions`, the response includes `currency: "USD"` (or `null` if not set)
- A `null` `currency` is treated as "same as home currency" — no rate lookup is performed
- When I create a manual transaction via `POST /transactions`, I can optionally provide `currency`; it defaults to `null`
- When a transaction is parsed from a statement, `currency` is `null` (no symbol-sniffing in v1 — the parser does not attempt to infer currency from "$", "₱", etc.)
- When I `PATCH /transactions/{id}`, I can update `currency` (including setting it to `null` to reset to home-currency assumption)

**In scope**: `currency VARCHAR(3) NULL` column on `transactions`; alembic migration (existing rows stay `null`); currency field in `TransactionCreate`, `TransactionPatch`, `TransactionOut` schemas; currency picker on manual-entry form.
**Out of scope**: Currency symbol detection from OCR/parsed text; bulk currency assignment; per-statement currency default.

**Touched files**: `backend/src/domain/models/transaction.py`, `backend/src/api/schemas/transactions.py`, `backend/src/api/routes/transactions.py`, `frontend/src/app/transactions/page.tsx`, `frontend/src/lib/types.ts`, `backend/alembic/versions/`.

**Contract delta**: see `contracts/currency.md §transactions`.

---

#### Story 7.3 — Historical exchange rate cache
> As the system, I want to cache historical exchange rates locally after fetching them once, so that multi-currency analytics work offline and don't re-fetch rates on every query.

**Acceptance criteria**
- Given an analytics query needs the rate for (2019-03-15, USD → PHP)
- When the `exchange_rates` table does not contain that pair+date
- Then the system calls `GET https://api.frankfurter.app/2019-03-15?from=USD&to=PHP`, stores the result, and uses it
- When the table already contains the pair+date, no network call is made
- When Frankfurter returns 404 or a network error (unavailable date, unsupported currency, offline), the rate is absent; the calling transaction is counted in `unconverted_count`
- Weekend/holiday dates with no ECB rate: Frankfurter returns the nearest prior business day's rate; the system stores it keyed to the **requested** date (not the returned date) to avoid re-fetching
- `POST /exchange-rates/prefetch` accepts `{from_currency, to_currency, start_date, end_date}` and pre-fetches all daily rates in that range (for offline-first users who want to seed before disconnecting)
- `GET /exchange-rates/supported` returns the list of currency codes Frankfurter supports (fetched from `https://api.frankfurter.app/currencies` and cached in memory / a config file)
- Outbound calls use a configurable timeout (default 5 s); failure surfaces in `unconverted_count`, never as a 5xx on the analytics endpoint

**Privacy note**: Frankfurter is an external outbound call, which contradicts the "all processing local" goal. Rate data contains no PII (only dates and currency codes). Users can fully mitigate this by running `POST /exchange-rates/prefetch` once while online, then operating offline. A fully bundled offline rate table is a future story.

**In scope**: `exchange_rates` table; `ExchangeRateService` (fetch + cache); Frankfurter HTTP client (`httpx`); prefetch endpoint; supported-currencies endpoint.
**Out of scope**: IMF/World Bank historical data for pre-1999 or exotic currencies not in Frankfurter (R8, R9); background periodic refresh; rate-change alerts; manual rate override UI.

**New dependency**: `httpx` (async HTTP client) — already used by FastAPI ecosystem; identity-check at implementation start: `pip show httpx`.

**Touched files**: new `backend/src/domain/services/exchange_rate.py`, new `backend/src/api/routes/exchange_rates.py`, new `backend/src/api/schemas/exchange_rates.py`, `backend/src/domain/models/` (new `exchange_rate.py` model), `backend/alembic/versions/`.

**Contract delta**: see `contracts/currency.md §exchange-rates`.

---

#### Story 7.4 — Multi-currency analytics aggregation
> As a user, I want my spending analytics to total all transactions in my home currency, so that I can compare and sum spending across currencies in a single number.

**Acceptance criteria**
- Given my home currency is `"PHP"` and I have transactions in USD and PHP
- When I call `GET /analytics/by-category?month=2024-03`
- Then the USD transactions are converted to PHP at each transaction's date rate; PHP transactions pass through at 1:1
- And the response includes `display_currency: "PHP"` and `unconverted_count: 0` (or N if any rates were missing)
- And the `?display_currency=USD` override converts everything to USD instead, for ad-hoc comparison
- And if `home_currency` is null (not yet configured), the response returns `display_currency: null` and `totals_available: false` with a `"detail": "Set home_currency in /settings to enable currency conversion"` advisory (not a 4xx — data still returns in original currencies per row)
- The same conversion logic applies to `GET /analytics/cash-flow`
- Conversion happens server-side in Python; converted amounts are never persisted

**In scope**: Conversion logic in analytics service; `display_currency`, `unconverted_count` added to all analytics response shapes; `?display_currency=` query param.
**Out of scope**: Per-category display currency; export in converted currency; transaction-level converted amounts in the list endpoint (Story 7.5 stretch).

**Touched files**: `backend/src/api/routes/analytics.py`, `backend/src/api/schemas/analytics.py` (if separate), `frontend/src/components/charts/SpendingDonut.tsx`, `frontend/src/components/charts/CashFlowBar.tsx`, `frontend/src/lib/types.ts`.

**Contract delta**: see `contracts/currency.md §analytics`.

---

#### Story 7.6 — Daily CI pipeline: autopopulate exchange rate artifact
> As a self-hosting user, I want a pre-seeded exchange rate database shipped with the project, so that historical analytics work out of the box without requiring any live Frankfurter calls on first run.

**Acceptance criteria**
- Given a GitHub Actions cron workflow runs daily at 03:00 UTC
- When it runs, it downloads the current `exchange_rates.db` artifact from the `rates-latest` GitHub Release (or starts fresh if none exists)
- Then fetches any missing dates from Frankfurter (incremental: only dates not already in the DB) and appends them
- And publishes the updated `.db` as an asset on the `rates-latest` release tag (rolling update — tag is force-moved; old asset replaced)
- A `workflow_dispatch` input `backfill: true` triggers a full historical fetch from 1999-01-04 to today (one-time seed)
- On first `docker compose up`, a one-shot `rates-init` service downloads the artifact into the `exchange_rates_data` volume if the file is absent or empty; the `backend` service `depends_on: rates-init: condition: service_completed_successfully`
- `RATES_DB_URL` env var controls where the bootstrap downloads from (default: the GH Releases URL); overridable for air-gapped / custom mirrors
- After bootstrap, on-demand Frankfurter fetch (Story 7.3) fills any gap between the artifact's cutoff date and today (at most ~24 h of missing rates)

**Fetch strategy**
- Backfill: single Frankfurter time-series call `GET /1999-01-04..{today}?from=USD` — returns all dates in one JSON response (~9k dates, ~30 rates each)
- Incremental: `GET /latest?from=USD` — appends the most recent business day's rates
- Both directions stored per fetch: `USD→X` from the response, `X→USD` as `1/rate`

**In scope**: `.github/workflows/rates-update.yml` (cron + `workflow_dispatch`); `.github/scripts/update_rates.py` (fetch + SQLite write); `rates-init` service in `docker-compose.yml`; `RATES_DB_URL` env var in `.env.example`.
**Out of scope**: Signed artifact checksums (v1); multi-base-currency artifact (USD base covers all needed pairs via transitivity); private registry mirror support.

**Touched files**: `.github/workflows/rates-update.yml` (new), `.github/scripts/update_rates.py` (new), `docker-compose.yml`, `.env.example`.

**Contract delta**: see `contracts/currency.md §ci-pipeline`.

---

#### Story 7.5 — Currency display in transaction list *(stretch)*
> As a user, I want to see the original currency and a home-currency equivalent on each transaction, so that I know what a foreign charge actually cost me.

**Acceptance criteria**
- Given a transaction with `currency: "USD"`, `amount: "72.50"`, and home_currency `"PHP"`
- When `GET /transactions?with_conversion=true` is called
- Then the response for that transaction includes `converted_amount: "4250.00"` and `converted_currency: "PHP"` (or both null if rate unavailable or currency already matches home)
- The UI shows the original amount prominently and the home equivalent in a secondary line: `₱4,250.00` / `USD 72.50`
- Transactions with `currency: null` do not show a secondary line (already in home currency)

**In scope**: `?with_conversion=true` query param on `GET /transactions`; per-row server-side conversion using the same `ExchangeRateService` as Story 7.3; frontend secondary-line display.
**Out of scope**: Live rate (always transaction-date rate); conversion in CSV export.

**Touched files**: `backend/src/api/routes/transactions.py`, `backend/src/api/schemas/transactions.py`, `frontend/src/app/transactions/page.tsx`, `frontend/src/lib/types.ts`.

---

### Alternatives considered for E7

**Alt A — Store baked home-currency amounts on each transaction**
Faster analytics queries (no join to exchange_rates). Rejected: amounts go stale when the user changes home currency or when a better rate becomes available. The original amount + currency is the ground truth; derived fields must be recomputable.

**Alt B — Client-side conversion**
Frontend fetches rates and converts amounts in the browser. Rejected: cannot aggregate accurately (would need all transaction amounts client-side before summing), and exposes the same Frankfurter call from the browser (no caching benefit).

**Alt C — Bundled static rates table (offline-first)**
Ship a pre-built SQLite/CSV table of daily rates from 1990–present. No external calls ever. Tradeoff: large artifact (~100 MB for all pairs, ~10 MB for common 30 currencies), must be updated to stay current, adds a build-time data pipeline. Not rejected — ideal long-term, but too much scope for the first iteration. Proposed as the "offline fallback" future story referenced in R10.

**Alt D — Open Exchange Rates API instead of Frankfurter**
More currencies, USD base (convenient for USD users). Requires free-tier account registration — contradicts privacy-first more than Frankfurter (no account needed). ECB/Frankfurter data quality is equivalent for the major pairs this app needs. PHP is in Frankfurter.

---

---

### E8: Account Profiles & Multi-Account Ledger

**Outcome**: Every transaction belongs to a named account (checking, savings, credit card, cash). Uploads auto-detect which account they belong to via a cryptographic fingerprint. Transfers between accounts are detected and excluded from cash-flow totals so nothing is double-counted.

**Central architectural decision — account-scoped transactions**: `transactions.account_id` becomes a required FK. Every transaction is owned by an account. Analytics are computed per-account or across selected accounts. Without this, a CC payment appearing on both the checking statement (debit) and the CC statement (credit) would count twice in cash flow.

**Privacy decision — HMAC fingerprinting**: Card and bank account numbers are never stored. On account creation the user optionally enters the full number; the system stores `hmac(APP_SECRET, full_number)` (a constant keyed hash using an env-var secret) and the last four digits in plaintext. On upload, OCR extracts the number from the statement header and the fingerprint is recomputed and looked up. If `APP_SECRET` leaks, no account numbers are recoverable. If `APP_SECRET` is lost, all fingerprints become unmatchable — R13.

---

#### Story 8.1 — Account management
> As a user, I want to create and name my accounts, so that I can track each card and bank account separately.

**Acceptance criteria**
- Given the Accounts page
- When I create an account with name, type, currency, opening balance, and opening date
- Then `POST /accounts` persists it and it appears in the account selector on upload and manual entry
- When I delete an account, transactions are soft-orphaned (`account_id` → null), not deleted
- `GET /accounts` returns all active accounts with computed `current_balance` (opening_balance + credits − debits since opening_date)

**In scope**: `accounts` table (`id`, `name`, `type ENUM(checking,savings,credit_card,cash)`, `currency`, `institution`, `last_four`, `opening_balance`, `opening_date`, `fingerprint`, `is_active`); alembic migration; CRUD routes; balance computation.
**Out of scope**: Account merge, account transfer history, multi-user ownership.

**New schema**:
```sql
accounts
  id               SERIAL PK
  name             VARCHAR(100) NOT NULL
  type             ENUM(checking, savings, credit_card, cash) NOT NULL
  currency         VARCHAR(3) NOT NULL DEFAULT 'USD'
  institution      VARCHAR(100)
  last_four        VARCHAR(4)        -- plaintext, display only
  fingerprint      VARCHAR(64)       -- hmac(APP_SECRET, full_number), nullable
  opening_balance  NUMERIC(12,2) NOT NULL DEFAULT 0
  opening_date     DATE NOT NULL
  is_active        BOOLEAN NOT NULL DEFAULT true

transactions
  account_id       INT REFERENCES accounts(id)   -- was nullable, now required for new rows
  transfer_peer_id INT REFERENCES transactions(id) NULLABLE  -- links both legs of a transfer
```

**Touched files**: new `backend/src/domain/models/account.py`, `backend/src/api/routes/accounts.py`, `backend/src/api/schemas/accounts.py`, `backend/src/domain/models/transaction.py`, `backend/alembic/versions/`, `frontend/src/app/accounts/page.tsx`.

---

#### Story 8.2 — Account fingerprint registration
> As a user, I want to register my card or account number when I create an account, so that the system can automatically recognise which account future uploads belong to.

**Acceptance criteria**
- Given I am creating an account
- When I optionally enter the full card or bank account number in the creation form
- Then the frontend sends only `last_four` and the number to `POST /accounts`; the backend computes `fingerprint = hmac(APP_SECRET, number)` and discards the raw number immediately — it is never stored or logged
- The creation response returns `last_four` but never the fingerprint or original number
- If I skip the number, `fingerprint` is null and auto-detection does not fire for this account

**In scope**: HMAC computation in the accounts route (Python `hmac.new(APP_SECRET.encode(), number.encode(), hashlib.sha256).hexdigest()`); `APP_SECRET` env var with validation at startup (must be ≥ 32 chars); number field accepted but not persisted.
**Out of scope**: Fingerprint update after account creation (new story); key rotation.

**Touched files**: `backend/src/core/config.py`, `backend/src/api/routes/accounts.py`.

---

#### Story 8.3 — Statement-to-account auto-detection on upload
> As a user, I want the app to automatically recognise which account a statement belongs to, so that I don't have to manually assign it every time.

**Acceptance criteria**
- Given a CC or bank statement is uploaded
- When OCR extracts the card or account number from the statement header (first page, top region)
- Then the backend computes its fingerprint and queries `accounts.fingerprint`
- If a match is found: the statement and all its transactions are assigned to that account automatically; the response includes `account_id` and `account_name`
- If no match is found: the response includes `account_id: null` and a `"detail": "Account not recognised — please assign manually"` advisory (not a 4xx); the frontend prompts the user to pick or create an account
- If fingerprinting is skipped (number not extractable from OCR): fall back to the manual prompt

**In scope**: Account number extraction regex patterns for CC statements (16-digit groups) and bank account numbers; fingerprint lookup; `statement.account_id` FK; transaction `account_id` set at bulk-insert time.
**Out of scope**: Per-page account detection for combined statements; multi-account statements.

**Touched files**: `backend/src/domain/services/statement_parser.py`, `backend/src/api/routes/statements.py`, `backend/src/domain/models/statement.py`, `frontend/src/app/upload/page.tsx`.

---

#### Story 8.3b — Auto-create account on first detection; fail if undetectable
> As a user, I want the system to create a new account automatically the first time it sees a card number, so that I don't have to set up accounts before my first upload — but I also want the upload to fail clearly if no account can be identified at all.

**Acceptance criteria**

*Path A — number detected, fingerprint matches existing account*
- Given OCR extracts a card or account number from the statement
- When `hmac(APP_SECRET, number)` matches an existing `accounts.fingerprint`
- Then the statement is auto-assigned to that account and upload proceeds (same as Story 8.3 match path)

*Path B — number detected, no fingerprint match (first upload for this card)*
- Given OCR extracts a number but no fingerprint match is found
- When the upload completes parsing
- Then the backend auto-creates an account: `name = "****{last_four}"`, `type` inferred from statement format (`credit_card` for CC statements, `checking` for bank statements), `currency = home_currency`, `opening_balance = 0`, `opening_date = today`
- The fingerprint and `last_four` are stored on the new account
- The statement and its transactions are assigned to the new account
- The response includes `account_created: true`, `account_id`, `account_name`
- The frontend shows a dismissable banner: **"New account created: ****9012 — tap to set opening balance and name"** linking to the Accounts edit page
- The user can optionally reassign to an existing account from the upload result screen (toggle: "Use existing account instead") — this triggers `PATCH /statements/{id}` with `account_id` and re-assigns all transactions

*Path C — no number detectable from OCR*
- Given OCR runs but cannot extract any card or account number (no 16-digit group, no account number pattern)
- Then the upload returns `HTTP 422` with `"detail": "Could not identify an account from this statement. Please use an account number visible on the document, or upload again and select an account manually."`
- No transactions are saved; `statements.status = "failed"` with the error message
- The frontend shows the error prominently and offers a "Select account manually" path that re-submits the upload with an explicit `account_id` in the request

**In scope**: Number extraction regex (16-digit CC groups, common bank account number formats); auto-create on fingerprint miss; `account_created` field in upload response; banner UI; manual re-submit with `account_id`; 422 on undetectable.
**Out of scope**: Receipt uploads (no account number on receipts — handled by Story 8.4); multi-account statements; IBAN/SWIFT formats (future).

**Touched files**: `backend/src/api/routes/statements.py`, `backend/src/domain/services/statement_parser.py`, `backend/src/api/routes/accounts.py`, `frontend/src/app/upload/page.tsx`.

---

#### Story 8.4 — Receipt upload → cash or card transaction
> As a user, I want to photograph a receipt and have the system log it as a transaction, so that cash and tap-to-pay purchases are captured without a statement.

**Acceptance criteria**
- Given I upload a receipt image (PNG/JPEG)
- When OCR extracts merchant name, date, and total
- And OCR finds a card indicator ("Visa ••••9012", "Mastercard", "Cash")
- Then the frontend shows a confirmation screen: inferred merchant, amount, date, and a "Paid with" selector pre-filled with the matched account (by last_four) or "Cash" if no card indicator
- When I confirm, `POST /transactions` creates a manual transaction (no `statement_id`) on the selected account
- If OCR cannot extract a total, the form pre-fills empty and user completes manually

**In scope**: Receipt OCR reusing the existing image pipeline; merchant/total/date/card-indicator extraction; "Paid with" confirmation UI; manual transaction creation on the chosen account.
**Out of scope**: Line-item receipt parsing (only totals in v1); loyalty card numbers; split payments.

**Touched files**: `backend/src/domain/services/statement_parser.py` (receipt mode), `backend/src/api/routes/statements.py`, `frontend/src/app/upload/page.tsx`.

---

#### Story 8.5 — Cross-statement duplicate detection with review UI
> As a user, I want the system to flag likely duplicate transactions after an upload, so that overlapping statement date ranges don't inflate my totals.

**Acceptance criteria**
- Given a statement is uploaded and transactions are parsed
- When a parsed transaction's `(account_id, amount, direction)` matches an existing transaction within ±3 calendar days
- Then that transaction is inserted with `duplicate_status = "suspected"` (not skipped — the user decides)
- The upload response includes `suspected_duplicate_count: N`
- `GET /transactions?duplicate_status=suspected` returns suspected duplicates for review
- For each suspected duplicate, the UI shows side-by-side: the existing row and the new row
- The user can: **Keep both** (clears `duplicate_status`), **Discard new** (soft-deletes the new row), or **Replace old** (soft-deletes the existing row, clears `duplicate_status` on new)
- Soft-deleted rows are excluded from all analytics and lists by default; `?include_deleted=true` shows them

**New fields on `transactions`**: `duplicate_status ENUM(null, suspected, confirmed_keep, confirmed_discard)`, `deleted_at TIMESTAMP`.

**In scope**: Duplicate detection on upload; suspected-duplicate endpoint; review UI (side-by-side card); soft-delete; analytics exclusion of deleted rows.
**Out of scope**: Retroactive duplicate scan on existing data; fuzzy description matching (amount + date window only in v1).

**Touched files**: `backend/src/domain/models/transaction.py`, `backend/src/api/routes/statements.py`, `backend/src/api/routes/transactions.py`, `backend/src/api/schemas/transactions.py`, `frontend/src/app/transactions/page.tsx`.

---

#### Story 8.6 — Transfer detection between accounts
> As a user, I want the system to detect when a debit on one account matches a credit on another (e.g. a CC payment), so that transfers are excluded from my cash-flow totals and nothing is counted twice.

**Acceptance criteria**
- Given I have a checking account and a CC account
- When a debit of ₱15,000 appears on checking on 2024-03-05 and a credit of ₱15,000 appears on the CC account within ±3 days
- Then both transactions are flagged `transfer_status = "suspected"` and linked via `transfer_peer_id`
- The UI shows a "Suspected transfer" banner with both legs for confirmation
- When I confirm: both rows keep `transfer_peer_id` and `transfer_status = "confirmed"` — analytics exclude them from debit/credit totals (they are neither income nor expense)
- When I dismiss: `transfer_status` cleared on both, treated as regular transactions
- Transfer detection runs automatically after each upload and can be triggered manually via `POST /transfers/detect`

**New fields on `transactions`**: `transfer_peer_id INT REFERENCES transactions(id)`, `transfer_status ENUM(null, suspected, confirmed, dismissed)`.

**In scope**: Amount + date-window matching across accounts; `transfer_peer_id` link; analytics exclusion; review UI; manual detect endpoint.
**Out of scope**: Cross-currency transfer matching (same-currency only in v1); partial transfers.

**Touched files**: new `backend/src/domain/services/transfer_detector.py`, `backend/src/api/routes/transactions.py`, `backend/src/domain/models/transaction.py`, `frontend/src/app/transactions/page.tsx`.

---

### E8 Risk additions

| ID | Risk | Class | Mitigation |
|---|---|---|---|
| R13 | `APP_SECRET` loss makes all fingerprints unmatchable; uploads revert to manual assignment | KNOWN | Document backup requirement; future story: fingerprint re-registration flow after key rotation |
| R14 | OCR may fail to extract card/account numbers from some statement layouts (logos obscuring numbers, unusual formatting) | [ASSUMPTION] | Fall back to manual account assignment prompt; never block upload |
| R15 | Transfer detection false positives (two unrelated same-amount transactions on different accounts within 3 days) | [ASSUMPTION] | Always require user confirmation; never auto-confirm transfers; dismiss path clears the flag cleanly |

---

### E9: Investment Accounts

**Outcome**: Users can track a brokerage account alongside their bank and CC accounts. Buy/sell transactions record symbol, shares, and price. Portfolio holdings show cost basis. No live price data in v1 — value is always at cost.

**Scope boundary**: Investment transactions are structurally different from spending transactions (symbol × shares × price, not just amount). They share the `accounts` table (a broker account is just another account type) but use an `investment_transactions` table rather than extending `transactions`. Cash deposits/withdrawals to the broker account appear in `transactions` normally.

---

#### Story 9.1 — Broker account type
> As a user, I want to add a broker account, so that I can track my investments alongside my cash accounts.

**Acceptance criteria**
- Given the Accounts page
- When I create an account with `type = broker`
- Then it appears in the accounts list with a distinct icon
- `GET /accounts/{id}/balance` for a broker account returns `cost_basis` (total amount invested at purchase price) rather than a cash balance
- Cash movements to/from the broker (deposits, withdrawals, dividends) are recorded as regular `transactions` on the broker account with `direction = credit/debit`

**In scope**: `broker` added to the `account_type` enum; broker account creation and listing; balance endpoint returning cost basis for broker accounts.
**Out of scope**: Live market prices, P&L, unrealised gains.

**Touched files**: `backend/src/domain/models/account.py`, `backend/src/api/routes/accounts.py`, `frontend/src/app/accounts/page.tsx`.

---

#### Story 9.2 — Investment transaction ingestion
> As a user, I want to upload a brokerage statement so that my buy and sell transactions are logged with symbol, shares, and price.

**Acceptance criteria**
- Given a brokerage statement (PDF or screenshot) is uploaded and the account is `type = broker`
- When the parser extracts rows with: date, symbol (e.g. `AAPL`), shares, price per share, direction (`buy` / `sell`), and optional commission
- Then records are created in `investment_transactions` with those fields; `amount = shares × price_per_share` is computed and stored
- `GET /accounts/{id}/investment-transactions` returns the list sorted by date descending
- If a row cannot be parsed (missing symbol or price), it is skipped and included in `parse_errors` in the response

**New table**:
```sql
investment_transactions
  id               SERIAL PK
  account_id       INT REFERENCES accounts(id) NOT NULL
  statement_id     INT REFERENCES statements(id)
  date             DATE NOT NULL
  symbol           VARCHAR(20) NOT NULL   -- ticker, e.g. "AAPL", "BRK.B"
  shares           NUMERIC(18, 6) NOT NULL
  price_per_share  NUMERIC(18, 6) NOT NULL
  amount           NUMERIC(18, 2) NOT NULL  -- shares × price, stored for audit
  direction        ENUM(buy, sell) NOT NULL
  commission       NUMERIC(12, 2)
  currency         VARCHAR(3) NOT NULL DEFAULT 'USD'
```

**In scope**: New `investment_transactions` table and migration; broker-aware branch in the upload pipeline; investment transaction parser (symbol + shares + price extraction); `GET /accounts/{id}/investment-transactions`.
**Out of scope**: Options, ETFs with NAV, fractional shares display rounding UI, DRIPs.

**Touched files**: new `backend/src/domain/models/investment_transaction.py`, new `backend/src/domain/services/investment_parser.py`, `backend/src/api/routes/statements.py`, new `backend/src/api/routes/investment_transactions.py`, `backend/alembic/versions/`.

---

#### Story 9.3 — Portfolio holdings view
> As a user, I want to see my current holdings with cost basis per position, so that I know what I own and what I paid for it.

**Acceptance criteria**
- Given I have buy and sell investment transactions for `AAPL`
- When I open the Portfolio page for my broker account
- Then I see each symbol with: shares held (buys − sells), average cost per share (weighted average of buys), total cost basis (shares held × avg cost)
- Positions with 0 shares held (fully sold) are hidden by default; `?include_closed=true` shows them
- No live prices in v1 — a "last price" column shows `—` with a note "Connect a price source (future feature)"

**In scope**: Holdings aggregation query (group by symbol, sum shares by direction, weighted avg cost); portfolio page; closed-position filter.
**Out of scope**: Live quotes, unrealised P&L, IRR, tax-lot accounting.

**Touched files**: new `backend/src/api/routes/portfolio.py`, new `frontend/src/app/portfolio/page.tsx`.

---

### E9 Risk additions

| ID | Risk | Class | Mitigation |
|---|---|---|---|
| R16 | Brokerage statement formats vary more than bank statements; symbol extraction will miss edge cases | [ASSUMPTION] | Parser returns `parse_errors` for unrecognised rows; user can manually add investment transactions |
| R17 | No live price data means portfolio value is always stale (cost basis only) | KNOWN | Explicitly documented in the UI; live price feed is a future story requiring a market data API key |
| R18 | `shares × price` floating-point precision for fractional shares | KNOWN | Use `NUMERIC(18,6)` throughout; never `FLOAT` |

---

## Decision

DSN-T6

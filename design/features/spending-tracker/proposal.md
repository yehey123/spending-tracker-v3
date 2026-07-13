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
├── docker-compose.yml              ← Postgres + backend
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

#### Story 2.2 — Edit transaction category
> As a user, I want to reassign a transaction's category, so that my spending breakdown is accurate.

**Acceptance criteria**
- Given a transaction in the list
- When I select a new category from the dropdown
- Then `PATCH /transactions/{id}` updates `category_id`
- And the dashboard immediately reflects the change

**In scope**: Category reassignment; description edit.
**Out of scope**: Bulk recategorization, rules engine.

**Touched files**: `backend/src/api/routes/transactions.py`, `frontend/src/app/transactions/page.tsx`.

---

#### Story 2.3 — Delete transaction
> As a user, I want to delete a transaction, so that I can remove duplicates or parsing errors.

**Acceptance criteria**
- Given a transaction row
- When I confirm deletion
- Then `DELETE /transactions/{id}` removes it and returns 204
- And it disappears from the list and analytics

**In scope**: Single delete with confirmation.
**Out of scope**: Bulk delete, undo.

**Touched files**: `backend/src/api/routes/transactions.py`.

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

#### Story 5.1 — Manage categories
> As a user, I want to create, rename, recolor, and delete spending categories, so that the breakdown matches my mental model.

**Acceptance criteria**
- Given the Categories screen
- When I create a category with a name and color
- Then `POST /categories` persists it and it appears in the transaction category picker
- When I delete a category that has transactions
- Then those transactions' `category_id` is set to null (Uncategorized), not deleted

**In scope**: CRUD for categories; cascade null on delete; color picker.
**Out of scope**: Category icons in v1 (field exists in schema, UI deferred), hierarchical categories.

**Touched files**: `backend/src/api/routes/categories.py`, `backend/src/domain/models/category.py`, `frontend/src/app/settings/page.tsx`.

---

## Decision

DSN-T6

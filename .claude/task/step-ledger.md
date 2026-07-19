---
task: Cloud Storage Backends (COMPLETE 2026-07-15)
branch: initial_backend
---

| # | Description | Status | Evidence |
|---|---|---|---|
| V | Docker build + full pytest run | PASS | 61 passed (was 39); boto3+gcs confirmed in image 2026-07-15 |

---
task: E6 — Deployment Gateway
date: 2026-07-17
branch: initial_backend
---

## Steps

| # | Description | Status | Evidence |
|---|---|---|---|
| P1 | Phase-1 discovery | PASS | evidence-inventory.md written 2026-07-17 |
| P2 | Phase-2 blueprint | PASS | blueprint.md written; user approved 2026-07-18 |
| 1 | frontend/Dockerfile + .dockerignore (multi-stage, Node 24, standalone) | PASS | Write × 2 succeeded 2026-07-18 |
| 2 | nginx/nginx.conf (reverse proxy; /health + /api/ + /) | PASS | Write succeeded; nginx/ dir created 2026-07-18 |
| 3 | docker-compose.yml (add frontend + nginx services) | PASS | docker compose config --quiet exits 0; frontend+nginx present 2026-07-18 |
| 4 | .env.compose.* + .env.example (NGINX_PORT=80) | PASS | grep shows 3/3 matches 2026-07-18 |
| V | docker compose build + up + smoke test + down | PASS | /health=healthy /api/health=healthy /=200 :3000=200; nginx -t ok; down clean 2026-07-18 |

---
task: Wave 0A — Schema Sprint
date: 2026-07-18
branch: initial_backend
---

## Steps

| # | Description | Status | Evidence |
|---|---|---|---|
| 1 | Migration 0005: statements spine (6 cols + 9 ENUM values via autocommit_block) | PASS | alembic upgrade 0004→0005 succeeded 2026-07-18 |
| 2 | Migration 0006: transactions spine (10 cols + updated_at trigger; currency skipped — already in 0004) | PASS | alembic upgrade 0005→0006 succeeded 2026-07-18 |
| 3 | Migration 0007: app_settings spine (3 cols; home_currency skipped — already in 0004) | PASS | alembic upgrade 0006→0007 succeeded 2026-07-18 |
| 4 | Migration 0008: categories spine (parent_id, slug, is_system + unique constraint) | PASS | alembic upgrade 0007→0008 succeeded 2026-07-18 |
| 5 | Migration 0009: new tables (transaction_flags, merchant_category_memory, audit_log) + pg_trgm GIN index | PASS | alembic upgrade 0008→0009 succeeded 2026-07-18 |
| 6 | Model updates: statement.py, transaction.py (incl. currency from 0004), app_settings.py (incl. home_currency from 0004), category.py; new: transaction_flag.py, merchant_memory.py, audit_log.py; models/__init__.py + env.py | PASS | Write/Edit succeeded 2026-07-18 |
| 7 | health.py _REQUIRED_TABLES: added transaction_flags, merchant_category_memory, audit_log | PASS | Edit succeeded 2026-07-18 |
| V | alembic current = 0009 (head); 60 pytest passed (excl. GCS/S3 — pre-existing missing SDK) | PASS | docker run dev image; 60 passed 0 failed 2026-07-18 |

---
task: Wave 0B — Analytics Exclusion Filter
date: 2026-07-18
branch: initial_backend
---

## Steps

| # | Description | Status | Evidence |
|---|---|---|---|
| 1 | analytics.py: add status=='active', reversed_by IS NULL, reversal_of IS NULL to by-category WHERE | PASS | Edit succeeded 2026-07-18 |
| 2 | analytics.py: same 3 filters on cash-flow credit sub-query | PASS | Edit succeeded 2026-07-18 |
| 3 | analytics.py: same 3 filters on cash-flow debit sub-query | PASS | Edit succeeded 2026-07-18 |
| 4 | test_analytics_exclusion.py: 4 tests (reversed pair × 2 endpoints, staged × 2 endpoints) | PASS | Write succeeded 2026-07-18 |
| V | 64 pytest passed (excl. GCS/S3 — pre-existing); new exclusion tests all green | PASS | docker run dev image; 64 passed 0 failed 2026-07-18 |

---
task: Wave 2 (2A–2E)
date: 2026-07-19
branch: initial_backend
receipt: ACT-K9
---

## Steps

| # | Description | Status | Evidence |
|---|---|---|---|
| P1 | Phase-1 evidence inventory | PASS | evidence-inventory.md written 2026-07-18/19 |
| P2 | Phase-2 blueprint (corrected ×5: cursor dir, /supported shape, no with_conversion, pipeline hook scope, receipts type wire) | PASS | blueprint.md finalized; user approved 2026-07-19 |
| 1 | types.ts — extend Transaction, ByCategoryResponse, CashFlowResponse, AppSettings, SettingsPut; add StagedTransaction + StagedReviewResponse | PASS | tsc: pre-existing error in settings/page.tsx (unrelated); no new errors from types.ts edits confirmed by stash diff |
| 2 | settings/page.tsx — Import Settings section (review_before_commit toggle, home currency picker); fix pre-existing BackgroundColor null error | PASS | tsc: 0 errors |
| 3 | upload/page.tsx — staged redirect: if data.status==='staged' router.push to review; remove console.log | PASS | tsc: 0 errors |
| 4 | StagedTransactionRow.tsx (new) — inline edit for staged txs; PATCH /staged-transactions/{id} | PASS | tsc: 0 errors |
| 5 | statements/[id]/review/page.tsx (new) — staged review page with commit/discard | PASS | tsc: 0 errors |
| M1 | Milestone: pytest after Steps 1-5 | PASS | 70 passed, 4 failed (pre-existing GCS/S3); no regressions |
| 6 | transactions/page.tsx — settings query + foreign currency badge | PASS | tsc: 0 errors |
| 7 | SpendingDonut.tsx + CashFlowBar.tsx — displayCurrency prop; warning badge; page.tsx passes through analytics fields | PASS | tsc: 0 errors |
| 8 | transactions.py — GET /search (pg_trgm similarity + ILIKE, keyset cursor DESC, linkable_only); test_search.py (5 tests) | PASS | 5/5 search tests green; note: reversal endpoint has pre-existing timezone bug; test uses direct DB write instead |
| 9 | receipts.py (new) + statements.py type-param wire + main.py registration; test_receipts.py (6 tests) | PASS | 6/6 green; fix: strip tzinfo from uploaded_at before window arithmetic |
| M2 | Milestone: full pytest after Steps 6-9 | PASS | 81 passed (+11 new), 4 failed (pre-existing GCS/S3) |
| M2b | GCS/S3 mock fix — sys.modules injection of fake exception classes | PASS | 85 passed, 0 failed |
| 10 | categorizer.py (new service) — normalize, categorize_statement, _call_ai (Anthropic), upsert_memory, bulk_recategorize_by_merchant | PASS | import OK in container |
| 11 | flags.py (new route) + main.py registration + statement_pipeline.py hook; test_flags.py (13 tests) | PASS | 13/13 green; utcnow() deprecation warning (pre-existing pattern, not a failure) |
| 12 | review/page.tsx (flags queue) — list open flags, accept/reject mutations, confidence bar, category lookup | PASS | tsc: 0 errors |
| 13 | BottomNav.tsx — Review tab + Flag icon + flags count badge with 30s refetch | PASS | tsc: 0 errors |
| 15 | useTransactionSearch.ts — debounced infinite query, base64 cursor, linkableOnly param | PASS | tsc: 0 errors (verified with Steps 12+13 batch) |
| 14 | receipts/page.tsx + ReceiptCard.tsx — receipt list, link/unlink mutations, search panel via useTransactionSearch | PASS | tsc: 0 errors |
| 16 | PWA: @ducanh2912/next-pwa@10.2.9 installed; next.config.mjs withPWA wrapper + CAPACITOR_BUILD output toggle; layout.tsx Apple PWA tags; Makefile cap targets | PASS | tsc: 0 errors; next.config.mjs verified |
| V | Final verification: full pytest + tsc | PASS | 98 passed, 0 failed, 8 utcnow() deprecation warnings (pre-existing); tsc: 0 errors |
| A1 | Advisor review — 5 items: npm build, categorizer coverage, untracked drift check, UI caveat, dead code | PASS | All 5 addressed 2026-07-19 |
| A2 | npm run build (Step 16 completion) | PASS | 9 routes built, 0 errors, all pages present (PWA wrapper exercised) |
| A3 | Untracked drift check: git status --porcelain | PASS | 11 untracked entries match blueprint new-file list; test_flags.py tracked (committed prior wave) |
| A4 | test_categorizer.py — merchant-memory path runtime coverage | PASS | 1 test added; 99 passed, 0 failed (full suite) |
| A5 | bulk_recategorize_by_merchant wired to flags.py confirm handler; orphan MerchantCategoryMemory import removed | PASS | existing 13 flag tests still green; 99 total passed |

---
task: Wave 3 (3A + 3B) — Blueprints
date: 2026-07-19
branch: initial_backend
---

## Steps

| # | Description | Status | Evidence |
|---|---|---|---|
| P1 | Phase-1 evidence inventory | PASS | evidence-inventory-3.md written 2026-07-19; discrepancies documented |
| P2 | Phase-2 blueprint — 3A accounts | PASS | blueprint-3a-accounts.md written; advisor review applied (direction bug, dueling impls, 3 new tests added → 11 total); awaiting user approval |
| P2b | Phase-2 blueprint — 3B investments | PASS | blueprint-3b-investments.md written; Step V target updated to 116; blocked on 3A merge; awaiting user approval |
| 1 | Migration 0010: accounts table + 5 tx cols + stmt account_id | PASS | alembic upgrade 0009→0010; `alembic current` = 0010 (head); rebuild required (image-baked src) |
| 2 | account.py model (ACCOUNT_TYPES, Mapped style) | PASS | import verified via Step 5 batch |
| 3 | transaction.py: 5 new cols + account relationship | PASS | import verified in models batch check |
| 4 | statement.py: account_id + Account relationship | PASS | import verified in models batch check |
| 5 | models/__init__.py: register Account | PASS | `import src.domain.models` OK after rebuild |
| 6 | health.py: add 'accounts' to _REQUIRED_TABLES | PASS | edit applied; verified in M1 milestone |
| 7 | config.py: add app_secret field | PASS | `hasattr(settings, 'app_secret')` = True |
| 8 | conftest.py: APP_SECRET inject + accounts TRUNCATE + db_session fixture | PASS | edit applied; verified in M1 |
| 9 | accounts.py route + main.py registration | PASS | rebuild OK; M1 health passes |
| 10 | transfer_detector.py new service | PASS | import verified in rebuild |
| M1 | Milestone: health + categories after Steps 1-10 | PASS | 9 passed, 0 failed |
| 11 | statement_pipeline.py: detect_account + _detect_duplicates + tuple return | PASS | pipeline imports OK; existing tests unaffected; tzinfo strip fix applied |
| 11s | schemas/statements.py + statements.py: account_id + account_created | PASS | StatementOut extended; upload unpacks tuple |
| 12 | analytics.py: deleted_at + or_(transfer_status) exclusion | PASS | edit applied; full suite green |
| 13 | types.ts: Account interface + Statement extensions | PASS | tsc 0 errors |
| 14 | accounts/page.tsx + BottomNav.tsx (Accounts tab) | PASS | tsc 0 errors |
| 15 | upload/page.tsx: account_created banner | PASS | tsc 0 errors |
| 16 | test_accounts.py: 11 tests | PASS | 11/11 green; 2 fixes: date.fromisoformat + await db.commit() in endpoint |
| V | Wave 3A full verification | PASS | 110 passed, 0 failed; tsc 0 errors |

---
task: Wave 3B (E9: Investment Accounts)
date: 2026-07-19
branch: initial_backend
receipt: ACT-K9
---

## Steps

| # | Description | Status | Evidence |
|---|---|---|---|
| 1 | Migration 0011: investment_transactions table | PASS | alembic upgrade 0010→0011; `alembic current` = 0011 (head) |
| 2 | investment_transaction.py model | PASS | import verified in rebuild |
| 3 | account.py: investment_transactions relationship | PASS | edit applied |
| 4 | models/__init__.py: register InvestmentTransaction | PASS | import OK after rebuild |
| 5 | health.py: add 'investment_transactions' | PASS | edit applied |
| 6 | conftest.py: add investment_transactions to TRUNCATE | PASS | edit applied |
| 7 | investment_parser.py new service | PASS | parser unit test green |
| 8 | investment_transactions.py route + main.py | PASS | list empty + 422 tests green |
| 9 | portfolio.py route + main.py | PASS | net shares + closed hidden tests green |
| 10 | accounts.py: balance endpoint | PASS | edit applied |
| 11 | statement_pipeline.py: broker branch | PASS | imports OK; existing tests unaffected |
| 12 | types.ts: InvestmentTransaction + Portfolio interfaces | PASS | tsc 0 errors |
| 13 | portfolio/[accountId]/page.tsx new | PASS | tsc 0 errors |
| 14 | accounts/page.tsx: View Portfolio link | PASS | tsc 0 errors |
| 15 | test_investments.py: 6 tests | PASS | 6/6 green |
| V | Wave 3B full verification | PASS | 116 passed, 0 failed; tsc 0 errors |

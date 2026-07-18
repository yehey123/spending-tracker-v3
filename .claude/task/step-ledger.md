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

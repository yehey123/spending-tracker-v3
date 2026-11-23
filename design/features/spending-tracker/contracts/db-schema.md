# Database Schema Contract — Spending Tracker

Engine: PostgreSQL 16. Async driver: asyncpg. ORM: SQLAlchemy 2.x (mapped_column style).

---

## Table: categories

| Column | Type | Constraints | Default |
|---|---|---|---|
| id | INTEGER | PK, auto-increment | — |
| name | VARCHAR(100) | NOT NULL, UNIQUE (case-insensitive via index) | — |
| color | VARCHAR(7) | NOT NULL | `'#6B7280'` |
| icon | VARCHAR(50) | NULL | NULL |

Indexes:
- `ix_categories_name` — UNIQUE, `lower(name)` (enforces case-insensitive uniqueness)

---

## Table: statements

| Column | Type | Constraints | Default |
|---|---|---|---|
| id | INTEGER | PK, auto-increment | — |
| filename | VARCHAR(255) | NOT NULL | — |
| file_path | VARCHAR(512) | NOT NULL | — |
| type | ENUM('credit_card_screenshot','bank_pdf') | NOT NULL | — |
| status | ENUM('pending','processing','done','failed') | NOT NULL | `'pending'` |
| ocr_provider | VARCHAR(50) | NULL | NULL |
| error_message | VARCHAR(1000) | NULL | NULL |
| uploaded_at | TIMESTAMP | NOT NULL | `NOW()` |

---

## Table: transactions

| Column | Type | Constraints | Default |
|---|---|---|---|
| id | INTEGER | PK, auto-increment | — |
| date | TIMESTAMP | NOT NULL | — |
| amount | NUMERIC(12,2) | NOT NULL, CHECK (amount > 0) | — |
| description | VARCHAR(500) | NOT NULL | — |
| direction | ENUM('debit','credit') | NOT NULL | — |
| category_id | INTEGER | FK → categories.id, ON DELETE SET NULL | NULL |
| statement_id | INTEGER | FK → statements.id, ON DELETE SET NULL | NULL |

Indexes:
- `ix_transactions_date` — for date-range queries
- `ix_transactions_category_id`
- `ix_transactions_statement_id`

---

## Table: app_settings

Single-row table (id always = 1, enforced at application layer).

| Column | Type | Constraints | Default |
|---|---|---|---|
| id | INTEGER | PK | 1 |
| ocr_provider | VARCHAR(50) | NOT NULL | `'tesseract'` |
| anthropic_api_key | VARCHAR(200) | NULL | NULL |
| openai_api_key | VARCHAR(200) | NULL | NULL |

The AI key and model columns on this table (`anthropic_api_key`, `openai_api_key`, `gemini_api_key`, `ai_model`, `google_project_id`, `google_location`, `max_output_tokens`) are kept in core but are owned by the AI plugin (`spending-tracker-ai`). Core does not read them directly; plugin descriptors declare them in `config_fields`. No migration was made when AI moved to the plugin.

Seeded on first startup: INSERT … ON CONFLICT DO NOTHING (id=1, provider='tesseract').

---

## Auth note (future pivot)
Add `user_id` FK to `transactions`, `statements`, `categories` when auth lands. Tables are designed without it now but the FK addition is a non-breaking migration (nullable column, backfill to a single default user record).

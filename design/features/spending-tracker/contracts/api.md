# API Contract — Spending Tracker Backend

Base URL: configurable by user (stored in frontend `localStorage`).
All requests/responses: `application/json` unless noted.
Error shape (all 4xx/5xx):
```json
{ "detail": "<human-readable message>" }
```

---

## Health

### GET /health
Response 200:
```json
{ "status": "healthy" }
```
Response 503:
```json
{ "detail": "Database unhealthy: <reason>" }
```

---

## Statements

### POST /statements/upload
Upload a statement file for parsing.

Request: `multipart/form-data`
- `file` (required): PNG, JPEG, or PDF — max 20 MB
- `type` (optional): `"credit_card_screenshot"` | `"bank_pdf"` — inferred from MIME if omitted

Response 200:
```json
{
  "id": 1,
  "filename": "statement_jan.pdf",
  "type": "bank_pdf",
  "status": "done",
  "ocr_provider": "tesseract",
  "transaction_count": 34,
  "uploaded_at": "2026-01-15T10:00:00Z"
}
```

Response 400:
```json
{ "detail": "Unsupported file type. Accepted: PNG, JPEG, PDF." }
```
```json
{ "detail": "Password-protected PDFs are not supported." }
```

Response 422: Pydantic validation error (standard FastAPI shape).

### GET /statements
List uploaded statements.

Query params:
- `limit` (int, default 20, max 100)
- `offset` (int, default 0)

Response 200:
```json
[
  {
    "id": 1,
    "filename": "statement_jan.pdf",
    "type": "bank_pdf",
    "status": "done",
    "ocr_provider": "tesseract",
    "transaction_count": 34,
    "uploaded_at": "2026-01-15T10:00:00Z",
    "error_message": null
  }
]
```

### DELETE /statements/{id}
Deletes the statement record and its file. Cascades to transactions (sets `statement_id = null`; does NOT delete transactions).

Response 204: No body.
Response 404: `{ "detail": "Statement not found." }`

---

## Transactions

### GET /transactions
List transactions.

Query params:
- `month` (string, optional): `"YYYY-MM"` — filter by month
- `category_id` (int, optional)
- `direction` (string, optional): `"debit"` | `"credit"`
- `limit` (int, default 50, max 200)
- `offset` (int, default 0)

Response 200:
```json
[
  {
    "id": 42,
    "date": "2026-01-05T00:00:00Z",
    "amount": "1500.00",
    "description": "GRAB FOOD",
    "direction": "debit",
    "category_id": 3,
    "category": { "id": 3, "name": "Food & Dining", "color": "#F59E0B" },
    "statement_id": 1
  }
]
```

### POST /transactions
Create a manual transaction (no statement source).

Request body:
```json
{
  "date": "2026-01-10T00:00:00Z",
  "amount": "250.00",
  "description": "Palengke",
  "direction": "debit",
  "category_id": 3
}
```

Validation:
- `date`: required, ISO 8601
- `amount`: required, positive decimal string, max 10 digits + 2 decimal places
- `description`: required, 1–500 chars
- `direction`: required, `"debit"` | `"credit"`
- `category_id`: optional, must exist if provided

Response 201: Full transaction object (same shape as GET item).

### PATCH /transactions/{id}
Update category and/or description. Partial update — omitted fields unchanged.

Request body (all fields optional):
```json
{
  "category_id": 5,
  "description": "Corrected description"
}
```

Response 200: Updated transaction object.
Response 404: `{ "detail": "Transaction not found." }`

### DELETE /transactions/{id}
Response 204: No body.
Response 404: `{ "detail": "Transaction not found." }`

---

## Categories

### GET /categories
Response 200:
```json
[
  { "id": 1, "name": "Food & Dining", "color": "#F59E0B", "icon": null },
  { "id": 2, "name": "Transport", "color": "#3B82F6", "icon": null }
]
```

### POST /categories
Request body:
```json
{ "name": "Utilities", "color": "#8B5CF6" }
```
Validation:
- `name`: required, 1–100 chars, unique (case-insensitive)
- `color`: required, hex color string matching `#[0-9A-Fa-f]{6}`

Response 201: `{ "id": 5, "name": "Utilities", "color": "#8B5CF6", "icon": null }`
Response 409: `{ "detail": "Category 'Utilities' already exists." }`

### PUT /categories/{id}
Full replace (same validation as POST, all fields required).

Response 200: Updated category object.
Response 404: `{ "detail": "Category not found." }`

### DELETE /categories/{id}
Sets `category_id = null` on all linked transactions. Does not delete transactions.

Response 204: No body.
Response 404: `{ "detail": "Category not found." }`

---

## Analytics

### GET /analytics/by-category
Spending (debits only) grouped by category for a given month.

Query params:
- `month` (string, required): `"YYYY-MM"`

Response 200:
```json
{
  "month": "2026-01",
  "total_debit": "18450.00",
  "breakdown": [
    { "category_id": 1, "category_name": "Food & Dining", "color": "#F59E0B", "amount": "5200.00", "percent": 28.2 },
    { "category_id": null, "category_name": "Uncategorized", "color": "#6B7280", "amount": "1100.00", "percent": 5.9 }
  ]
}
```

### GET /analytics/cash-flow
Monthly inflow/outflow totals.

Query params:
- `months` (int, default 6, max 24): how many months back to include

Response 200:
```json
{
  "months": [
    {
      "month": "2026-01",
      "total_credit": "50000.00",
      "total_debit": "18450.00",
      "net": "31550.00"
    }
  ]
}
```

---

## Settings

### GET /settings
Returns current OCR configuration. API keys are masked.

Response 200:
```json
{
  "ocr_provider": "tesseract",
  "anthropic_api_key_set": false,
  "openai_api_key_set": false
}
```

### PUT /settings
Update OCR provider and/or API keys. Omit a key field to leave it unchanged; send `null` to clear it.

Request body:
```json
{
  "ocr_provider": "claude",
  "anthropic_api_key": "sk-ant-...",
  "openai_api_key": null
}
```

Validation:
- `ocr_provider`: `"tesseract"` | `"claude"` | `"openai"`
- If `ocr_provider` = `"claude"`, `anthropic_api_key` must be set (either now or already stored)
- If `ocr_provider` = `"openai"`, `openai_api_key` must be set

Response 200:
```json
{
  "ocr_provider": "claude",
  "anthropic_api_key_set": true,
  "openai_api_key_set": false
}
```

Response 422: Provider requires a key that is neither in the request nor already stored.

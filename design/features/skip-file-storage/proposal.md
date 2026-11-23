# Design Proposal: Skip File Storage After OCR Processing

**Status**: ACCEPTED
**Date**: 2026-07-25
**Rationale**: Files are write-only (never read back), storage adds latency and cost with no active consumer. Stories 1.1 and 1.2 accepted; Story 2.1 (drop column) deferred.

---

## 1. Summary, Goals, Non-Goals

### Summary

Statement and receipt files are currently saved to a storage backend (local disk / S3 / GCS)
on upload, but are **never read back** — no endpoint calls `storage.get()`. The pipeline
receives `content` in memory and processes it directly; `raw_ocr_text` and `file_hash` land
in the DB; the raw file sits in storage unused. This proposal removes the write entirely:
process in memory, discard the bytes, keep nothing on disk or in the cloud.

### Goals

- Zero cloud storage cost for uploaded files.
- Remove the upload latency penalty of writing to S3/GCS before OCR starts.
- Fix the existing TTL-cleanup bug where expired staged statements leave orphaned files in
  storage (currently `ttl_cleanup.py` discards the DB row but never calls `storage.delete()`).
- Simplify the upload path: one less async I/O step, one less failure mode.

### Non-Goals

- Changing OCR logic, pipeline stages, or categorization.
- Removing the `StorageBackend` abstraction (still used if exchange-rate DB or other assets
  need storage in future).
- Changing how `raw_ocr_text`, `file_hash`, or transaction data are stored in the DB.
- Re-processing from original file (see Alternatives — this becomes impossible; accepted tradeoff).

---

## 2. Evidence

All grounded in tool calls, not assumptions:

| Claim | Evidence |
|---|---|
| Files are never read back | `grep storage.get src/` → 0 hits across all backend source files |
| Re-run endpoints not implemented | `statements.py` has no `/ocr`, `/parse`, `/categorize` routes; design proposal lists them as future scope |
| TTL cleanup leaks files | `ttl_cleanup.py:22-35` — discards staged statements, never calls `storage.delete()` |
| Cloud storage design's own non-goal | `cloud-storage-backends/proposal.md` §1 Non-Goals: *"Serving/streaming files back to the client — files are write-once, processed in-memory, not re-served"* |
| `file_hash` computed in memory | `statement_pipeline.py:204` — `hashlib.sha256(content)` uses the in-memory `content`, not a stored file |
| `storage_key` column would become dead | `statement.py:37` — `storage_key` is set in upload route but read nowhere |

---

## 3. Pros / Cons

### Pros

- **Zero storage cost**: no bytes written to S3/GCS/local for uploaded statements or receipts.
- **Faster uploads**: `storage.save()` to a cloud backend adds 200–800 ms of latency before
  OCR even starts. Skipping it makes the upload endpoint respond faster.
- **Simpler failure surface**: `storage.save()` failing currently blocks the upload (line 54-55
  in `statements.py`); removing it eliminates a class of 500 errors.
- **Fixes TTL leak**: orphaned storage objects from expired staged statements no longer accumulate.
- **Consistent with stated design intent**: the cloud storage proposal already called files
  "write-once, processed in-memory, not re-served" — this makes the code match that statement.

### Cons

- **No re-OCR from original file**: if OCR quality is poor (wrong provider, model update),
  the user must re-upload the file manually. Mitigated by: `raw_ocr_text` is stored in DB
  so `parse` and `categorize` re-runs still work; only Stage 1 OCR is lost.
- **No audit trail of the original file**: in a dispute, the user cannot prove the transaction
  came from a specific file. Mitigated by: `file_hash`, `filename`, `uploaded_at`, and
  `raw_ocr_text` remain in the DB as a paper trail.
- **`storage_key` column becomes a dead field**: always NULL after this change. Can be left
  in place (no migration needed) or cleaned up in a follow-up.

---

## 4. Impact on Repo State

### Affected files

| File | Change |
|---|---|
| `backend/src/api/routes/statements.py:51-55` | Remove `storage = get_storage_backend()` + `await storage.save(key, content)` block |
| `backend/src/api/routes/statements.py:50` | Remove `key = f"{uuid.uuid4()}.{ext}"` (key no longer needed) |
| `backend/src/api/routes/statements.py:57-59` | Remove `storage_key=key` from `Statement(...)` constructor |
| `backend/src/api/routes/statements.py:253-258` | Remove `storage.delete(statement.storage_key)` from `delete_statement` |
| `backend/src/tasks/ttl_cleanup.py` | Remove orphaned-file concern (already not deleting — becomes correct by default) |
| `backend/src/domain/models/statement.py:37` | `storage_key` column remains but is always NULL — optional follow-up migration to drop it |

### What does NOT change

- `StorageBackend` abstraction and all backends — kept for future use.
- `STORAGE_BACKENDS` config — kept, no env var churn.
- `file_hash`, `raw_ocr_text`, `filename`, `uploaded_at` — all stay in DB.
- All other pipeline stages (parse, categorize, commit, review).
- Receipt link/unlink/reassign flow — unaffected (uses DB only).

### Breaking changes

- `DELETE /statements/{id}` no longer deletes a storage object. No API contract change — the
  endpoint still returns 204 and deletes the DB row.
- `storage_key` column will always be NULL for new rows. Any consumer reading it gets `None`
  (currently there are none).

### Migrations

None required. `storage_key` can stay nullable and unused. A follow-up story can drop it if
desired.

### Test surface

- `tests/test_statements.py` — remove any assertions on `storage.save()` being called.
- `tests/services/test_storage_*.py` — unaffected (test the backends themselves, not the route).
- Add a test: upload succeeds even when `STORAGE_BACKENDS` is misconfigured (storage no longer
  called on upload path).

---

## 5. Alternatives

### A: Delete file immediately after successful OCR (store briefly, then purge)

Save → OCR → delete on success. Preserves re-OCR ability during the request window.
**Rejected**: adds complexity (need to handle partial failures), still incurs the write
latency, and the re-OCR window is 0 seconds in practice since OCR runs synchronously.

### B: Store with a short TTL (e.g. 24h), let bucket lifecycle rules purge

Keep current write, add S3/GCS object lifecycle policy for 1-day expiry.
**Rejected**: still pays write cost, requires per-bucket config outside this repo, and
the existing TTL cleanup already fails to call `storage.delete()` so the same leak would
persist for local storage.

### C: Make storage opt-in via a config flag (`KEEP_UPLOADED_FILES=true`)

Default to no storage, allow operators to opt in if they want re-OCR capability.
**Reasonable**: zero-cost default, escape hatch for power users.
**Deferred to out-of-scope**: adds a config branch; the re-OCR endpoint doesn't exist yet
so there's nothing to enable. Revisit if `POST /statements/{id}/ocr` is ever implemented.

---

## 6. Risk Register

| # | Risk | Class | Mitigation |
|---|---|---|---|
| R1 | A user needs to re-OCR from original after bad parse | ACCEPTED | Must re-upload; `raw_ocr_text` in DB covers re-parse/re-categorize |
| R2 | `storage_key` NULL causes a downstream consumer to break | [ASSUMPTION] no consumer exists | Grep confirms 0 callers of `storage_key` outside the upload route |
| R3 | Future re-OCR endpoint (`POST /statements/{id}/ocr` from design) would need the file | KNOWN | File will not be available; that story must re-upload or use `raw_ocr_text` instead |

---

## 7. Epics and Stories

### Epic 1 — Remove file write from upload path

#### Story 1.1 — Skip storage.save() on statement/receipt upload

> As a user, I want my statement upload to succeed without writing to cloud storage,
> so that uploads are faster and don't fail due to storage misconfigurations.

**Acceptance criteria**
- Given a valid PNG/JPEG/PDF upload
- When the upload endpoint is called
- Then OCR runs on the in-memory bytes, transactions are staged, and no file is written to storage
- And `statement.storage_key` is NULL
- Given `STORAGE_BACKENDS=gcs` and GCS credentials are absent
- When a file is uploaded
- Then the upload still succeeds (storage is not called)

**In scope**: Remove `storage.save()` call and `key` generation from `statements.py:upload_statement`.
**Out of scope**: Dropping the `storage_key` column; removing the storage abstraction.
**Touched files**: `backend/src/api/routes/statements.py`.

---

#### Story 1.2 — Remove storage.delete() from statement deletion

> As a user, I want statement deletion to work correctly even though no file was ever saved,
> so that `DELETE /statements/{id}` doesn't error on a missing storage object.

**Acceptance criteria**
- Given a committed statement with `storage_key = NULL`
- When `DELETE /statements/{id}` is called
- Then the statement and its DB row are deleted; no storage call is made; response is 204

**In scope**: Remove `storage.delete()` call from `delete_statement` in `statements.py`.
**Touched files**: `backend/src/api/routes/statements.py`.

---

### Epic 2 — Cleanup (optional follow-up)

#### Story 2.1 — Drop storage_key column

> As a developer, I want the dead `storage_key` column removed from the schema,
> so that the model accurately reflects what is actually stored.

**In scope**: Alembic migration to drop `statements.storage_key`; remove `Mapped` field from `statement.py`.
**Touched files**: `backend/src/domain/models/statement.py`, new migration.
**Note**: Non-breaking. Can be deferred indefinitely — NULL column costs nothing.

---

## 8. Scope by Layer

### Backend
- Remove `storage.save()` and `key` generation from `statements.py:upload_statement` (Story 1.1).
- Remove `storage.delete()` from `statements.py:delete_statement` (Story 1.2).
- `storage_key` field on `Statement` model becomes always-NULL; no model code change required for Epic 1.
- Optional: drop `storage_key` column via migration (Story 2.1).
- `StorageBackend` abstraction and all backend classes (`local.py`, `s3.py`, `gcs.py`, `mirrored.py`) are **unchanged** — kept for future use.

### Frontend
- **No changes.** The upload UI, review flow, and receipt linking screens are unaffected.
- No file URL or download link is currently surfaced to the user, so nothing breaks visually.

### DevOps / Infrastructure
- Cloud storage buckets (S3/GCS) can be removed or left empty — no objects will be written.
- `STORAGE_BACKENDS` env var can be left as-is or removed from `.env` / deployment config;
  the backend will simply never call the configured backend on the upload path.
- Bucket lifecycle rules (if any) can be removed — no objects to expire.
- Local `upload_dir` volume in `docker-compose.yml` can eventually be dropped (still referenced
  by `UPLOAD_DIR` config but no longer written to via the statement upload path).

### Automations / Background Tasks
- `ttl_cleanup.py` — no change needed. The current bug (not calling `storage.delete()` for
  expired staged statements) becomes a non-issue since no files are written in the first place.
- No new scheduled tasks required.

### CI / CD
- No pipeline changes required.
- Existing `tests/services/test_storage_*.py` tests continue to pass — they test the backend
  classes in isolation, not the upload route.
- New test in `tests/test_statements.py`: upload succeeds with `STORAGE_BACKENDS` unset or
  pointing to a nonexistent backend (confirms storage is no longer on the critical path).

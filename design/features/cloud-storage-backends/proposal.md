# Design Proposal: Cloud Storage Backends (S3 / GCS / Mirrored)

**Status**: ACCEPTED
**Date**: 2026-07-15
**Rationale**: Accepted with expanded scope — mirrored multi-backend added so local + S3 + GCS can be active simultaneously. `STORAGE_BACKEND` (single selector) replaced with `STORAGE_BACKENDS` (comma-separated list).

---

## 1. Summary, Goals, Non-Goals

### Summary

Replace the hard-wired local filesystem writes in the statement upload flow with a pluggable
`StorageBackend` abstraction. Four backends ship: `local` (existing behaviour, default),
`s3` (AWS S3 or any S3-compatible store), `gcs` (Google Cloud Storage), and `MirroredBackend`
(automatic fan-out to any combination of the above). The active backends are selected via
the `STORAGE_BACKENDS` env var (comma-separated); no code changes required to switch or combine.

### Goals

- Zero-change upgrade path: `STORAGE_BACKENDS=local` keeps existing behaviour exactly.
- Any combination of backends: `local,s3,gcs` mirrors to all three simultaneously.
- On mirrored save failure: rollback successful writes before raising.
- IAM-role / ADC credential chains supported (no hard-coded key requirement for cloud).
- Idiomatic async: cloud SDK calls wrapped in `asyncio.to_thread()`.
- S3-compatible stores (MinIO, Cloudflare R2, Backblaze B2) work via `AWS_*` vars + endpoint override.

### Non-Goals

- Serving/streaming files back to the client (files are write-once, processed in-memory, not re-served).
- Pre-signed URL generation for direct browser upload.
- Encryption at rest (handled by the bucket/storage policy, not this app).
- Per-file backend routing (all files go to all configured backends).
- Migration tooling for existing files already on disk (manual `aws s3 cp` / `gsutil cp`).

---

## 2. Pros / Cons

### Pros

- **Persistence across restarts**: cloud backends survive container recycles; local `/tmp` does not.
- **Redundancy**: mirrored mode keeps copies on-disk and in cloud simultaneously.
- **Scalable deployment**: multiple backend replicas can share a single bucket.
- **Minimal surface**: abstraction is two methods on one class; adding a fourth backend is a single file.
- **Default unchanged**: teams that don't want cloud storage see zero diff in behaviour.
- **Clean rollback on partial save**: mirrored save failure triggers rollback of succeeded backends.

### Cons

- **New dependencies**: `boto3` and `google-cloud-storage` are heavyweight even when unused. Mitigation: lazy import.
- **Sync SDK wrapping**: `asyncio.to_thread()` is correct but less efficient than native async clients. Acceptable for personal-finance scale.
- **Mirrored save is not atomic**: rollback is best-effort (a delete after a write failure can itself fail). This is documented in risk register and acceptable for this use case.
- **`file_path` column rename** requires an Alembic migration; existing deployments need the migration applied before the new code.

---

## 3. Impact on Current Repo State

### Affected files and current usages

| File | Change |
|---|---|
| `backend/src/core/config.py` | Replace `upload_dir` + add 9 new env vars (STORAGE_BACKENDS, AWS_*, GCS_*) |
| `backend/src/api/routes/statements.py:98-101` | Replace `os.makedirs + open(file_path, "wb")` with `await storage.save(key, content)` |
| `backend/src/api/routes/statements.py:217-218` | Replace `os.remove(file_path)` with `await storage.delete(key)` |
| `backend/src/domain/models/statement.py:26` | Rename column `file_path` → `storage_key`; update `Mapped` field name |
| `backend/alembic/versions/` | New migration: rename column + backfill data |
| `backend/requirements/base.txt` | Add `boto3>=1.34`, `google-cloud-storage>=2.17` |
| `.env.example` | Add storage env var block |
| `docker-compose.yml` | Add storage env var comments |
| `README.md` | Add storage backend section to env var table |

**New files**:
```
backend/src/domain/services/storage/
├── __init__.py      ← get_storage_backend() factory + _build_backend()
├── base.py          ← StorageBackend ABC + StorageError
├── local.py         ← LocalBackend
├── s3.py            ← S3Backend
├── gcs.py           ← GCSBackend
└── mirrored.py      ← MirroredBackend
```

### Breaking changes

- `Statement.file_path` ORM attribute renamed to `Statement.storage_key`. Consumers:
  `statements.py:106` (write) and `statements.py:217` (delete read) — both changed in Story 1.2.
  No other consumer (grep-confirmed above).
- `STORAGE_BACKEND` env var (never shipped) replaced by `STORAGE_BACKENDS`. No deployed users affected.
- `Statement.storage_key` stores a relative key, not an absolute path. Existing rows backfilled by migration.

### Migrations

One Alembic migration:
1. `UPDATE statements SET file_path = regexp_replace(file_path, '^.*/', '');`
2. `ALTER TABLE statements RENAME COLUMN file_path TO storage_key;`

Reversible: rename back, prepend `settings.upload_dir` to each row on downgrade.

### New dependencies (identity-checked)

| Package | PyPI name | Min version | When needed |
|---|---|---|---|
| `boto3` | `boto3` | `1.34` | `s3` in STORAGE_BACKENDS |
| `google-cloud-storage` | `google-cloud-storage` | `2.17` | `gcs` in STORAGE_BACKENDS |

Both conditionally imported (lazy, inside backend `__init__` or method bodies). Docker image size increase: ~15 MB combined.

### Test surface

- `test_statements.py`: 5 existing tests currently allow a real `open()` to `/tmp`. Post-change, tests inject a mock `StorageBackend` via `patch("src.api.routes.statements.get_storage_backend")`.
- New unit tests: `tests/services/test_storage_local.py`, `test_storage_s3.py` (mocked boto3), `test_storage_gcs.py` (mocked GCS client), `test_storage_mirrored.py` (mocked backends, covers partial-failure + rollback paths).

### Security notes

- AWS keys and GCS credentials are env vars — same secrets pattern as existing OCR keys.
- `GOOGLE_APPLICATION_CREDENTIALS` is a file path; the file must not be committed (already covered by `.gitignore`).
- Buckets must be **private**. The app never generates public URLs.
- `StorageError` message exposed in HTTP 500 detail must not embed credentials. Boto3 and GCS SDK exception messages do not contain credential material.

---

## 4. Alternatives Considered

### `fsspec` / `universal-pathlib`

Unified filesystem spec library wrapping local, S3, GCS, Azure behind a single `open()`.
Pros: minimal bespoke code, future backends for free.
Cons: heavy transitive dep tree (~30 MB), magic config via URL strings, harder to unit-test.
**Rejected** — bespoke abstraction is five files and two methods; dependency cost exceeds abstraction cost.

### `aioboto3` (native async S3)

Truly async S3 client. Pros: no thread-pool overhead.
Cons: separate package from `boto3`, less maintained, still wraps boto3 under the hood.
**Deferred** — can be swapped into `S3Backend` later without touching any other code.

### Single selector (`STORAGE_BACKEND=local|s3|gcs`)

Original design before user feedback. Simpler config but no mirroring capability.
**Superseded** by comma-separated `STORAGE_BACKENDS` which covers single-backend and mirrored without two separate config keys.

---

## 5. Risk Register

| # | Risk | Class | Mitigation |
|---|---|---|---|
| R1 | Existing data in `/tmp` lost after column rename if migration not run before deploy | KNOWN | Migration is required step before starting new container; README upgrade note |
| R2 | `asyncio.to_thread()` blocks event loop under upload surge | [ASSUMPTION] small user base | Acceptable for personal-finance scale; flag for revisit if multi-user auth added |
| R3 | GCS ADC not available in container → runtime failure | [UNKNOWN] | Factory probe: if `gcs` in STORAGE_BACKENDS, attempt a no-op auth check at startup and raise if it fails |
| R4 | Mirrored save rollback can itself fail (delete after a write failure fails) | KNOWN | Rollback errors are logged but do not suppress the original StorageError; orphaned objects are possible and acceptable (personal-finance scale, manual cleanup viable) |
| R5 | MinIO / R2 endpoint override not in initial scope | KNOWN non-goal | `AWS_ENDPOINT_URL` can be wired to boto3 client in follow-up; placeholder noted in contract |
| R6 | Duplicate backend names in STORAGE_BACKENDS (e.g. `s3,s3`) cause undefined fan-out | KNOWN | Factory raises `ValueError` on duplicate names at startup |

---

## 6. Epics → Stories → Scopes

---

### Epic 1 — Storage Abstraction Layer

Introduce the `StorageBackend` protocol and `LocalBackend`; wire the existing route to use it.
Functionally equivalent to today; sets the foundation for cloud and mirrored backends.

---

#### Story 1.1 — Storage interface + LocalBackend

**As a** backend developer,
**I want** a `StorageBackend` ABC and a `LocalBackend` implementation,
**so that** the upload route can be decoupled from `os.makedirs` / `open()` without changing observable behaviour.

**Acceptance criteria**
- Given `STORAGE_BACKENDS=local` (or unset), `LocalBackend` is returned by the factory.
- When `save(key, content)` is called, the file is written to `{UPLOAD_DIR}/{key}`.
- When `delete(key)` is called and the file does not exist, no exception is raised.
- When `delete(key)` is called and the file exists, it is removed.
- `StorageError` is raised (not `OSError`) on unrecoverable write failure.

**Scope**
- In: `backend/src/domain/services/storage/{base,local,__init__}.py` (new files)
- In: `backend/src/core/config.py` — rename `upload_dir`-only to add `storage_backends: str = "local"` alongside `upload_dir`
- Out: S3, GCS, mirrored backends, route changes, migration (later stories)
- Contract: `design/features/cloud-storage-backends/contracts/storage-interface.md`

**Delegation brief**
- `component`: BE
- `read-first`: `backend/src/core/config.py`, `design/features/cloud-storage-backends/contracts/storage-interface.md`
- `implement`: `StorageBackend` ABC + `StorageError` in `base.py`; `LocalBackend` in `local.py`; `_build_backend()` + `get_storage_backend()` factory skeleton (local branch only) in `__init__.py`; add `storage_backends: str = "local"` to `Settings`
- `no-touch`: `statements.py`, `statement.py` (Story 1.2 owns those)
- `rollback`: `git revert` the three new files + config.py change

---

#### Story 1.2 — Wire route + migration

**As a** developer deploying the app,
**I want** the upload and delete routes to use `StorageBackend`,
**so that** switching to S3, GCS, or mirrored requires only an env var change, no code change.

**Acceptance criteria**
- Given a PNG upload, `storage.save(key, content)` is called; `Statement.storage_key` stores the returned key.
- Given a statement delete, `storage.delete(key)` is called.
- Given an existing deployment, the Alembic migration renames `file_path` to `storage_key` and strips directory prefix from existing values.
- All 5 existing `test_statements.py` tests pass after patching `get_storage_backend` to return a mock backend.

**Scope**
- In: `backend/src/api/routes/statements.py:98-101, 217-218` — replace filesystem calls
- In: `backend/src/domain/models/statement.py:26` — rename `file_path` → `storage_key`
- In: `backend/alembic/versions/` — new migration
- Out: S3/GCS/mirrored backend files (Stories 2.1, 3.1, 4.1)
- After: Story 1.1

**Delegation brief**
- `component`: BE
- `read-first`: `backend/src/api/routes/statements.py`, `backend/src/domain/models/statement.py`, `backend/src/domain/services/storage/__init__.py` (written by 1.1), `design/features/cloud-storage-backends/contracts/storage-interface.md`
- `implement`: replace lines 98-101 and 217-218 with `await get_storage_backend().save(key, content)` and `await get_storage_backend().delete(key)`; rename `Statement.file_path` → `Statement.storage_key`; write Alembic migration per contract SQL
- `no-touch`: `storage/base.py`, `storage/local.py`, `storage/__init__.py` (Story 1.1 owns those)
- `rollback`: `git revert` statements.py + statement.py + migration file; `alembic downgrade -1`

---

### Epic 2 — S3 Backend

---

#### Story 2.1 — S3Backend implementation

**As a** user running the app on a cloud VM,
**I want** uploaded statement files stored in S3,
**so that** files persist independently of the container's ephemeral filesystem.

**Acceptance criteria**
- Given `STORAGE_BACKENDS=s3` and valid `AWS_S3_BUCKET`, factory returns `S3Backend`.
- When `save(key, content)` is called, `client.put_object(Bucket=..., Key=key, Body=content)` is invoked via `asyncio.to_thread()`.
- When `delete(key)` is called and the object does not exist, no exception is raised.
- `ClientError` → `StorageError` on write failure.
- Unit test mocks `boto3.client` and verifies `put_object` / `delete_object` called with correct args.

**Scope**
- In: `backend/src/domain/services/storage/s3.py` (new file)
- In: `backend/src/core/config.py` — add `aws_s3_bucket`, `aws_access_key_id`, `aws_secret_access_key`, `aws_region`
- In: `backend/src/domain/services/storage/__init__.py` — add `s3` branch to `_build_backend()`
- In: `backend/requirements/base.txt` — add `boto3>=1.34`
- In: `backend/tests/services/test_storage_s3.py` (new)
- Out: GCS, mirrored, docker-compose (Stories 3.1, 4.1, 2.2)
- After: Story 1.1 (parallel with 3.1)

**Delegation brief**
- `component`: BE
- `read-first`: `backend/src/domain/services/storage/base.py`, `backend/src/core/config.py`, `design/features/cloud-storage-backends/contracts/storage-interface.md`
- `implement`: `S3Backend` per contract; lazy `import boto3` inside methods; `asyncio.to_thread()` wrappers; `ClientError` → `StorageError`; add `s3` branch in `_build_backend()`; write unit test
- `no-touch`: `local.py`, `gcs.py`, `mirrored.py`, `statements.py`
- `rollback`: `git revert` s3.py + config.py + __init__.py + requirements changes

---

#### Story 2.2 — S3 config + docs

**As a** developer deploying to S3,
**I want** clear env var documentation and updated `.env.example`,
**so that** I know exactly what to set without reading source code.

**Acceptance criteria**
- `.env.example` contains commented `AWS_*` block with all 4 vars and note about IAM role alternative.
- `README.md` env var table includes S3 vars with "required when" column.
- `docker-compose.yml` contains commented S3 env var placeholders under `backend.environment`.

**Scope**
- In: `.env.example`, `README.md`, `docker-compose.yml`
- Out: backend code, GCS/mirrored docs
- After: Story 2.1 (parallel with Story 3.2)

**Delegation brief**
- `component`: DevOps
- `read-first`: `.env.example`, `README.md`, `docker-compose.yml`, `design/features/cloud-storage-backends/contracts/storage-interface.md`
- `implement`: add S3 env var block to all three files per contract configuration table
- `no-touch`: `backend/src/`, `frontend/`
- `rollback`: `git revert` the three doc files

---

### Epic 3 — GCS Backend

---

#### Story 3.1 — GCSBackend implementation

**As a** user running the app on GCP,
**I want** uploaded statement files stored in Google Cloud Storage,
**so that** files persist and integrate with GCP IAM and lifecycle policies.

**Acceptance criteria**
- Given `STORAGE_BACKENDS=gcs` and valid `GCS_BUCKET`, factory returns `GCSBackend`.
- When `save(key, content)` is called, `blob.upload_from_string(content)` is invoked via `asyncio.to_thread()`.
- When `delete(key)` is called and the blob does not exist, no exception is raised.
- `GoogleAPIError` → `StorageError` on write failure.
- ADC path: if `GOOGLE_APPLICATION_CREDENTIALS` is None, `Client()` uses ADC.
- Unit test mocks `google.cloud.storage.Client` and verifies blob methods called with correct args.

**Scope**
- In: `backend/src/domain/services/storage/gcs.py` (new file)
- In: `backend/src/core/config.py` — add `gcs_bucket`, `gcs_project_id`, `google_application_credentials`
- In: `backend/src/domain/services/storage/__init__.py` — add `gcs` branch to `_build_backend()`
- In: `backend/requirements/base.txt` — add `google-cloud-storage>=2.17`
- In: `backend/tests/services/test_storage_gcs.py` (new)
- Out: S3, mirrored, docker-compose (Stories 2.1, 4.1, 3.2)
- After: Story 1.1 (parallel with 2.1)

**Delegation brief**
- `component`: BE
- `read-first`: `backend/src/domain/services/storage/base.py`, `backend/src/core/config.py`, `design/features/cloud-storage-backends/contracts/storage-interface.md`
- `implement`: `GCSBackend` per contract; lazy `from google.cloud import storage` inside methods; `asyncio.to_thread()` wrappers; `GoogleAPIError` → `StorageError`; add `gcs` branch in `_build_backend()`; write unit test
- `no-touch`: `local.py`, `s3.py`, `mirrored.py`, `statements.py`
- `rollback`: `git revert` gcs.py + config.py + __init__.py + requirements changes

---

#### Story 3.2 — GCS config + docs

**As a** developer deploying to GCS,
**I want** clear env var documentation and updated `.env.example`,
**so that** I know what to set for both key-file and ADC auth.

**Acceptance criteria**
- `.env.example` contains commented `GCS_*` block with all 3 vars and note about ADC default.
- `README.md` env var table includes GCS vars.
- `docker-compose.yml` contains commented GCS env var placeholders.

**Scope**
- In: `.env.example`, `README.md`, `docker-compose.yml`
- Out: backend code, S3 docs
- After: Story 3.1 (parallel with Story 2.2)

**Delegation brief**
- `component`: DevOps
- `read-first`: `.env.example`, `README.md`, `docker-compose.yml`, `design/features/cloud-storage-backends/contracts/storage-interface.md`
- `implement`: add GCS env var block to all three files per contract table; note ADC default
- `no-touch`: `backend/src/`, `frontend/`
- `rollback`: `git revert` the three doc files

---

### Epic 4 — Mirrored Backend

Fan-out writes to any combination of backends simultaneously, with rollback on partial failure.

---

#### Story 4.1 — MirroredBackend implementation

**As a** user who wants local + cloud redundancy,
**I want** `STORAGE_BACKENDS=local,s3` (or any combination) to write to all named backends simultaneously,
**so that** I have on-disk copies and cloud copies without running separate upload commands.

**Acceptance criteria**
- Given `STORAGE_BACKENDS=local,s3`, factory returns `MirroredBackend([LocalBackend, S3Backend])`.
- Given `STORAGE_BACKENDS=local,s3,gcs`, factory returns `MirroredBackend([LocalBackend, S3Backend, GCSBackend])`.
- When `save(key, content)` is called, all backends receive the write concurrently via `asyncio.gather()`.
- When `save()` fails on ≥1 backend: rollback (delete) is called on all succeeded backends, then `StorageError` is raised naming the failed backends.
- When `delete(key)` is called, all backends' `delete()` are gathered; partial `StorageError` raises after all attempts complete.
- Duplicate backend names in `STORAGE_BACKENDS` raise `ValueError` at startup.
- Unit test covers: all-succeed, partial-save-failure-with-rollback, partial-delete-failure.

**Scope**
- In: `backend/src/domain/services/storage/mirrored.py` (new file)
- In: `backend/src/domain/services/storage/__init__.py` — parse comma-separated `STORAGE_BACKENDS`, invoke `MirroredBackend` when `len > 1`
- In: `backend/tests/services/test_storage_mirrored.py` (new)
- Out: individual backend implementations (Stories 2.1, 3.1), route code, docs
- After: Stories 2.1 and 3.1 (needs all three individual backends complete)

**Delegation brief**
- `component`: BE
- `read-first`: `backend/src/domain/services/storage/base.py`, `backend/src/domain/services/storage/__init__.py`, `design/features/cloud-storage-backends/contracts/storage-interface.md`
- `implement`: `MirroredBackend` per contract state machine; update `get_storage_backend()` to parse comma-separated list and call `MirroredBackend` when `len(backends) > 1`; write unit tests for all three outcome paths
- `no-touch`: `local.py`, `s3.py`, `gcs.py`, `statements.py`
- `rollback`: `git revert` mirrored.py + __init__.py changes

---

#### Story 4.2 — Mirrored config + docs

**As a** developer enabling mirrored storage,
**I want** the `STORAGE_BACKENDS` comma-separated syntax documented,
**so that** I know how to enable `local,s3` or `local,s3,gcs` without reading source code.

**Acceptance criteria**
- `README.md` env var table documents `STORAGE_BACKENDS` with valid value examples (table from contract).
- `.env.example` contains commented `STORAGE_BACKENDS=local` default with commented multi-backend examples.

**Scope**
- In: `.env.example`, `README.md`
- Out: backend code, individual backend docs (covered by 2.2, 3.2)
- After: Story 4.1 (parallel with nothing)

**Delegation brief**
- `component`: DevOps
- `read-first`: `.env.example`, `README.md`, `design/features/cloud-storage-backends/contracts/storage-interface.md`
- `implement`: add `STORAGE_BACKENDS` entry to README env var table with all valid combinations; update `.env.example`
- `no-touch`: `backend/src/`, `frontend/`, `docker-compose.yml`
- `rollback`: `git revert` the two doc files

---

### Epic 5 — S3-Compatible Endpoint Override (R2 / MinIO / Backblaze B2)

Closes R5 in the risk register. Allows `S3Backend` to target any S3-compatible store by accepting a custom endpoint URL.

---

#### Story 5.1 — `AWS_ENDPOINT_URL` support in S3Backend

**As a** user on Cloudflare R2 (or MinIO / Backblaze B2),
**I want** to point the S3 backend at a custom endpoint,
**so that** I get S3-compatible storage without an AWS account.

**Acceptance criteria**
- Given `AWS_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com` is set
- When `S3Backend._client()` is called, `boto3.client("s3", ..., endpoint_url=<value>)` is passed
- When `AWS_ENDPOINT_URL` is unset, behavior is identical to today (AWS endpoint, no regression)
- Unit test verifies `endpoint_url` is forwarded to `boto3.client` when set, and absent when not set

**Scope**
- In: `backend/src/domain/services/storage/s3.py` — add `endpoint_url: str | None = None` param to `__init__` and `_client()`
- In: `backend/src/core/config.py` — add `aws_endpoint_url: str | None = None`
- In: `backend/src/domain/services/storage/__init__.py` — pass `endpoint_url=settings.aws_endpoint_url` in the `s3` factory branch
- In: `.env.example` — add commented `AWS_ENDPOINT_URL` with R2 example
- In: `backend/tests/services/test_storage_s3.py` — add endpoint_url test case
- Out: GCS, local, mirrored backends; no docker-compose changes

**Delegation brief**
- `component`: BE
- `read-first`: `backend/src/domain/services/storage/s3.py`, `backend/src/domain/services/storage/__init__.py`, `backend/src/core/config.py`
- `implement`: two-line change to `s3.py` + one config field + factory wiring + `.env.example` comment
- `no-touch`: `gcs.py`, `local.py`, `mirrored.py`, `statements.py`
- `after`: Story 2.1

---

## Execution Rounds

```
Round 1 [sequential]:
  Story 1.1 — Storage interface + LocalBackend (BE)

Round 2 [parallel, after Round 1]:
  Story 1.2 — Wire route + migration (BE)
  Story 2.1 — S3Backend implementation (BE)
  Story 3.1 — GCSBackend implementation (BE)

Round 3 [parallel, after Round 2]:
  Story 2.2 — S3 config + docs (DevOps)
  Story 3.2 — GCS config + docs (DevOps)
  Story 4.1 — MirroredBackend implementation (BE)
  Story 5.1 — AWS_ENDPOINT_URL support (BE)

Round 4 [sequential, after Round 3]:
  Story 4.2 — Mirrored config + docs (DevOps)
```

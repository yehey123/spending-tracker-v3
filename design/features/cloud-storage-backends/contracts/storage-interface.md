# Contract: StorageBackend Interface

**Feature**: Cloud Storage Backends (S3 / GCS / Mirrored)
**Status**: ACCEPTED

---

## Abstract Interface

```python
# backend/src/domain/services/storage/base.py

from abc import ABC, abstractmethod


class StorageBackend(ABC):

    @abstractmethod
    async def save(self, key: str, content: bytes) -> str:
        """
        Persist `content` under `key`.
        Returns the canonical storage key (same as input key).
        Raises: StorageError on write failure.
        """

    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        Remove object at `key`.
        Silent no-op if key does not exist.
        Raises: StorageError on unexpected backend error.
        """


class StorageError(Exception):
    """Raised by any backend on unrecoverable IO failure."""
```

---

## Key Format

Keys are **relative, backend-agnostic identifiers** — never absolute paths.

| Pattern | Example |
|---|---|
| `{uuid}.{ext}` | `3f2a1b4c-...-9e0d.png` |

The `Statement.storage_key` column stores this value verbatim. Backends resolve the key to
a full location internally:

| Backend | Resolution |
|---|---|
| `local` | `{UPLOAD_DIR}/{key}` |
| `s3` | `s3://{AWS_S3_BUCKET}/{key}` |
| `gcs` | `gs://{GCS_BUCKET}/{key}` |

The `MirroredBackend` delegates resolution to each member backend independently.

---

## Local Backend

```python
# backend/src/domain/services/storage/local.py

class LocalBackend(StorageBackend):

    def __init__(self, upload_dir: str) -> None: ...

    async def save(self, key: str, content: bytes) -> str:
        # os.makedirs(upload_dir, exist_ok=True)
        # writes content to {upload_dir}/{key}
        # returns key

    async def delete(self, key: str) -> None:
        # os.remove({upload_dir}/{key}), ignores FileNotFoundError
```

---

## S3 Backend

```python
# backend/src/domain/services/storage/s3.py

class S3Backend(StorageBackend):

    def __init__(
        self,
        bucket: str,
        aws_access_key_id: str | None = None,   # None → IAM role / env chain
        aws_secret_access_key: str | None = None,
        region_name: str = "us-east-1",
    ) -> None: ...

    async def save(self, key: str, content: bytes) -> str:
        # boto3 client.put_object(Bucket=bucket, Key=key, Body=content)
        # wrapped in asyncio.to_thread()
        # ClientError → StorageError
        # returns key

    async def delete(self, key: str) -> None:
        # boto3 client.delete_object(Bucket=bucket, Key=key)
        # wrapped in asyncio.to_thread()
        # NoSuchKey → silent no-op; other ClientError → StorageError
```

---

## GCS Backend

```python
# backend/src/domain/services/storage/gcs.py

class GCSBackend(StorageBackend):

    def __init__(
        self,
        bucket: str,
        project: str | None = None,              # None → inferred from ADC
        credentials_file: str | None = None,     # None → ADC
    ) -> None: ...

    async def save(self, key: str, content: bytes) -> str:
        # google.cloud.storage.Client().bucket(bucket).blob(key).upload_from_string(content)
        # wrapped in asyncio.to_thread()
        # GoogleAPIError → StorageError
        # returns key

    async def delete(self, key: str) -> None:
        # blob.delete()
        # wrapped in asyncio.to_thread()
        # NotFound → silent no-op; other GoogleAPIError → StorageError
```

---

## Mirrored Backend

```python
# backend/src/domain/services/storage/mirrored.py

class MirroredBackend(StorageBackend):
    """
    Fans out every write to all member backends.
    On save() partial failure: successful writes are rolled back (delete called
    on each backend that succeeded) before raising StorageError.
    On delete() partial failure: all backends attempted; errors are collected
    and raised as a combined StorageError after all deletes run (best-effort).
    """

    def __init__(self, backends: list[StorageBackend]) -> None:
        # requires len(backends) >= 2
        ...

    async def save(self, key: str, content: bytes) -> str:
        # asyncio.gather(*[b.save(key, content) for b in backends], return_exceptions=True)
        # if any result is a StorageError:
        #   asyncio.gather(*[b.delete(key) for b in succeeded_backends], return_exceptions=True)
        #   raise StorageError(f"Mirrored save failed on: {failed_names}")
        # returns key

    async def delete(self, key: str) -> None:
        # asyncio.gather(*[b.delete(key) for b in backends], return_exceptions=True)
        # collect non-None results that are StorageError; if any:
        #   raise StorageError(f"Mirrored delete partial failure on: {failed_names}")
```

---

## Factory

```python
# backend/src/domain/services/storage/__init__.py

def _build_backend(name: str) -> StorageBackend:
    """Instantiate a single named backend from settings."""
    if name == "local":
        return LocalBackend(settings.upload_dir)
    if name == "s3":
        return S3Backend(
            bucket=settings.aws_s3_bucket,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
    if name == "gcs":
        return GCSBackend(
            bucket=settings.gcs_bucket,
            project=settings.gcs_project_id,
            credentials_file=settings.google_application_credentials,
        )
    raise ValueError(f"Unknown storage backend: {name!r}")


def get_storage_backend() -> StorageBackend:
    """
    Parse STORAGE_BACKENDS (comma-separated) and return the appropriate backend.
      "local"         → LocalBackend
      "s3"            → S3Backend
      "gcs"           → GCSBackend
      "local,s3"      → MirroredBackend([LocalBackend, S3Backend])
      "local,s3,gcs"  → MirroredBackend([LocalBackend, S3Backend, GCSBackend])
    Order in the list is preserved; duplicates are rejected at startup (ValueError).
    """
    names = [n.strip() for n in settings.storage_backends.split(",")]
    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate backends in STORAGE_BACKENDS: {names}")
    backends = [_build_backend(n) for n in names]
    if len(backends) == 1:
        return backends[0]
    return MirroredBackend(backends)
```

---

## Configuration Contract

All new env vars added to `backend/src/core/config.py`:

| Env Var | Type | Default | Required when |
|---|---|---|---|
| `STORAGE_BACKENDS` | `str` | `"local"` | always |
| `UPLOAD_DIR` | `str` | `"/tmp/spending-tracker-uploads"` | `local` in STORAGE_BACKENDS |
| `AWS_S3_BUCKET` | `str \| None` | `None` | `s3` in STORAGE_BACKENDS |
| `AWS_ACCESS_KEY_ID` | `str \| None` | `None` | `s3` in STORAGE_BACKENDS (or IAM role) |
| `AWS_SECRET_ACCESS_KEY` | `str \| None` | `None` | `s3` in STORAGE_BACKENDS (or IAM role) |
| `AWS_REGION` | `str` | `"us-east-1"` | `s3` in STORAGE_BACKENDS |
| `GCS_BUCKET` | `str \| None` | `None` | `gcs` in STORAGE_BACKENDS |
| `GCS_PROJECT_ID` | `str \| None` | `None` | `gcs` in STORAGE_BACKENDS (or ADC) |
| `GOOGLE_APPLICATION_CREDENTIALS` | `str \| None` | `None` | `gcs` in STORAGE_BACKENDS (or ADC) |

**Valid STORAGE_BACKENDS values** (any comma-separated combination):

| Value | Effect |
|---|---|
| `local` | Single local backend (default) |
| `s3` | Single S3 backend |
| `gcs` | Single GCS backend |
| `local,s3` | Mirror: local + S3 |
| `local,gcs` | Mirror: local + GCS |
| `s3,gcs` | Mirror: S3 + GCS |
| `local,s3,gcs` | Mirror: all three |

---

## Database Migration Contract

Column rename on `statements` table:

| | Before | After |
|---|---|---|
| Column name | `file_path` | `storage_key` |
| Type | `VARCHAR(512)` | `VARCHAR(512)` |
| Semantics | absolute local path | relative storage key |

**Data migration**: existing rows have absolute paths (e.g. `/tmp/.../abc.png`).
Migration extracts basename via `regexp_replace(file_path, '^.*/', '')` to convert to key form.

```sql
-- Alembic migration (op.execute)
UPDATE statements SET file_path = regexp_replace(file_path, '^.*/', '');
ALTER TABLE statements RENAME COLUMN file_path TO storage_key;
```

---

## Error Shape

Callers catch `StorageError` and convert to HTTP 500:

```json
{ "detail": "Storage error: <backend message>" }
```

For `MirroredBackend`, the message names the failed backends:

```json
{ "detail": "Storage error: Mirrored save failed on: s3, gcs" }
```

No storage-specific fields (bucket names, credentials) leak into API responses.

---

## Mirrored Save Failure State Machine

```
save(key, content)
  │
  ├─ gather all backends
  │     ├─ all succeed → return key ✓
  │     └─ ≥1 fails
  │           ├─ rollback: delete(key) on each that succeeded
  │           └─ raise StorageError("Mirrored save failed on: {names}")

delete(key)
  │
  ├─ gather all backends (ignore NotFound each)
  │     ├─ all succeed/NotFound → return ✓
  │     └─ ≥1 unexpected error
  │           └─ raise StorageError("Mirrored delete partial failure on: {names}")
  │              (all backends still attempted before raising)
```

from src.core.config import settings
from src.domain.services.storage.base import StorageBackend, StorageError
from src.domain.services.storage.gcs import GCSBackend
from src.domain.services.storage.local import LocalBackend
from src.domain.services.storage.mirrored import MirroredBackend
from src.domain.services.storage.s3 import S3Backend


def _build_backend(name: str) -> StorageBackend:
    if name == "local":
        return LocalBackend(settings.upload_dir)
    if name == "s3":
        return S3Backend(
            bucket=settings.aws_s3_bucket or "",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
    if name == "gcs":
        return GCSBackend(
            bucket=settings.gcs_bucket or "",
            project=settings.gcs_project_id,
            credentials_file=settings.google_application_credentials,
        )
    raise ValueError(f"Unknown storage backend: {name!r}")


def get_storage_backend() -> StorageBackend:
    """
    Parse STORAGE_BACKENDS (comma-separated) and return the appropriate backend.
      "local"      → LocalBackend
      "s3"         → S3Backend
      "gcs"        → GCSBackend
      "local,s3"   → MirroredBackend([LocalBackend, S3Backend])
    Duplicates (e.g. "s3,s3") raise ValueError at startup.
    """
    names = [n.strip() for n in settings.storage_backends.split(",")]
    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate backends in STORAGE_BACKENDS: {names}")
    backends = [_build_backend(n) for n in names]
    if len(backends) == 1:
        return backends[0]
    return MirroredBackend(backends)


__all__ = [
    "get_storage_backend",
    "StorageBackend",
    "StorageError",
    "LocalBackend",
    "S3Backend",
    "GCSBackend",
    "MirroredBackend",
]

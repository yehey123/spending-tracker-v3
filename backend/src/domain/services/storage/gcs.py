import asyncio

from src.domain.services.storage.base import StorageBackend, StorageError


class GCSBackend(StorageBackend):

    def __init__(
        self,
        bucket: str,
        project: str | None = None,
        credentials_file: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._project = project
        self._creds_file = credentials_file

    def _client(self):
        from google.cloud import storage  # lazy import — SDK not required at module load time
        if self._creds_file:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_file(self._creds_file)
            return storage.Client(project=self._project, credentials=creds)
        return storage.Client(project=self._project)

    async def save(self, key: str, content: bytes) -> str:
        try:
            client = self._client()
            bucket = client.bucket(self._bucket)
            blob = bucket.blob(key)
            await asyncio.to_thread(blob.upload_from_string, content)
        except Exception as e:
            raise StorageError(f"GCS write failed for key {key!r}: {e}") from e
        return key

    async def delete(self, key: str) -> None:
        try:
            client = self._client()
            bucket = client.bucket(self._bucket)
            blob = bucket.blob(key)
            await asyncio.to_thread(blob.delete)
        except Exception as e:
            # google.api_core.exceptions.NotFound → silent no-op
            try:
                from google.api_core.exceptions import NotFound
                if isinstance(e, NotFound):
                    return
            except ImportError:
                pass
            raise StorageError(f"GCS delete failed for key {key!r}: {e}") from e

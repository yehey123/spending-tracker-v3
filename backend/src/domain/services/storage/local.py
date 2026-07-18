import os

from src.domain.services.storage.base import StorageBackend, StorageError


class LocalBackend(StorageBackend):

    def __init__(self, upload_dir: str) -> None:
        self._upload_dir = upload_dir

    async def save(self, key: str, content: bytes) -> str:
        os.makedirs(self._upload_dir, exist_ok=True)
        path = os.path.join(self._upload_dir, key)
        try:
            with open(path, "wb") as fh:
                fh.write(content)
        except OSError as e:
            raise StorageError(f"Local write failed: {e}") from e
        return key

    async def delete(self, key: str) -> None:
        path = os.path.join(self._upload_dir, key)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError as e:
            raise StorageError(f"Local delete failed: {e}") from e

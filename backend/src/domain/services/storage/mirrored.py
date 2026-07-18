import asyncio

from src.domain.services.storage.base import StorageBackend, StorageError


class MirroredBackend(StorageBackend):
    """
    Fans out every write to all member backends concurrently.
    On save() partial failure: rolls back (deletes) on succeeded backends before raising.
    On delete() partial failure: attempts all backends, then raises combined StorageError.
    """

    def __init__(self, backends: list[StorageBackend]) -> None:
        if len(backends) < 2:
            raise ValueError("MirroredBackend requires at least 2 backends")
        self._backends = backends

    async def save(self, key: str, content: bytes) -> str:
        results = await asyncio.gather(
            *[b.save(key, content) for b in self._backends],
            return_exceptions=True,
        )
        failed = [
            (b, r) for b, r in zip(self._backends, results) if isinstance(r, Exception)
        ]
        if failed:
            succeeded = [
                b for b, r in zip(self._backends, results) if not isinstance(r, Exception)
            ]
            # Best-effort rollback on backends that succeeded
            await asyncio.gather(
                *[b.delete(key) for b in succeeded],
                return_exceptions=True,
            )
            names = ", ".join(type(b).__name__ for b, _ in failed)
            raise StorageError(f"Mirrored save failed on: {names}")
        return key

    async def delete(self, key: str) -> None:
        results = await asyncio.gather(
            *[b.delete(key) for b in self._backends],
            return_exceptions=True,
        )
        errors = [
            (b, r) for b, r in zip(self._backends, results) if isinstance(r, StorageError)
        ]
        if errors:
            names = ", ".join(type(b).__name__ for b, _ in errors)
            raise StorageError(f"Mirrored delete partial failure on: {names}")

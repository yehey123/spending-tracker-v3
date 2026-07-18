from abc import ABC, abstractmethod


class StorageBackend(ABC):

    @abstractmethod
    async def save(self, key: str, content: bytes) -> str:
        """Persist content under key. Returns the canonical key. Raises StorageError on failure."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove object at key. Silent no-op if key does not exist. Raises StorageError on error."""


class StorageError(Exception):
    """Raised by any backend on unrecoverable IO failure."""

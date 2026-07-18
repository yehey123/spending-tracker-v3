import pytest
from unittest.mock import AsyncMock, MagicMock

from src.domain.services.storage.base import StorageError
from src.domain.services.storage.mirrored import MirroredBackend


def _make_mock_backend(name: str = "MockBackend"):
    m = MagicMock()
    m.__class__.__name__ = name
    m.save = AsyncMock(return_value="key.png")
    m.delete = AsyncMock()
    return m


@pytest.mark.asyncio
async def test_save_all_succeed():
    a = _make_mock_backend("BackendA")
    b = _make_mock_backend("BackendB")
    mirrored = MirroredBackend([a, b])
    result = await mirrored.save("key.png", b"data")
    assert result == "key.png"
    a.save.assert_called_once_with("key.png", b"data")
    b.save.assert_called_once_with("key.png", b"data")


@pytest.mark.asyncio
async def test_save_partial_failure_rolls_back_succeeded():
    a = _make_mock_backend("BackendA")
    b = _make_mock_backend("BackendB")
    b.save.side_effect = StorageError("B failed")
    mirrored = MirroredBackend([a, b])
    with pytest.raises(StorageError, match="Mirrored save failed"):
        await mirrored.save("key.png", b"data")
    # A succeeded before B failed — rollback delete should be called on A
    a.delete.assert_called_once_with("key.png")


@pytest.mark.asyncio
async def test_save_all_fail_no_rollback():
    a = _make_mock_backend("BackendA")
    b = _make_mock_backend("BackendB")
    a.save.side_effect = StorageError("A failed")
    b.save.side_effect = StorageError("B failed")
    mirrored = MirroredBackend([a, b])
    with pytest.raises(StorageError, match="Mirrored save failed"):
        await mirrored.save("key.png", b"data")
    # Neither succeeded — no rollback deletes
    a.delete.assert_not_called()
    b.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_all_succeed():
    a = _make_mock_backend("BackendA")
    b = _make_mock_backend("BackendB")
    mirrored = MirroredBackend([a, b])
    await mirrored.delete("key.png")
    a.delete.assert_called_once_with("key.png")
    b.delete.assert_called_once_with("key.png")


@pytest.mark.asyncio
async def test_delete_partial_failure_raises_after_all_attempted():
    a = _make_mock_backend("BackendA")
    b = _make_mock_backend("BackendB")
    b.delete.side_effect = StorageError("B delete failed")
    mirrored = MirroredBackend([a, b])
    with pytest.raises(StorageError, match="Mirrored delete partial failure"):
        await mirrored.delete("key.png")
    # A was still called despite B's failure
    a.delete.assert_called_once_with("key.png")


@pytest.mark.asyncio
async def test_requires_at_least_two_backends():
    a = _make_mock_backend()
    with pytest.raises(ValueError):
        MirroredBackend([a])

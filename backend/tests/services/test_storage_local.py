import os
import pytest

from src.domain.services.storage.local import LocalBackend
from src.domain.services.storage.base import StorageError


@pytest.mark.asyncio
async def test_save_creates_file(tmp_path):
    backend = LocalBackend(str(tmp_path))
    key = "test-key.png"
    await backend.save(key, b"hello bytes")
    assert (tmp_path / key).read_bytes() == b"hello bytes"


@pytest.mark.asyncio
async def test_save_returns_key(tmp_path):
    backend = LocalBackend(str(tmp_path))
    result = await backend.save("abc.png", b"x")
    assert result == "abc.png"


@pytest.mark.asyncio
async def test_save_creates_upload_dir(tmp_path):
    upload_dir = str(tmp_path / "new" / "nested")
    backend = LocalBackend(upload_dir)
    await backend.save("file.png", b"data")
    assert os.path.exists(os.path.join(upload_dir, "file.png"))


@pytest.mark.asyncio
async def test_delete_existing(tmp_path):
    backend = LocalBackend(str(tmp_path))
    key = "to-delete.png"
    (tmp_path / key).write_bytes(b"data")
    await backend.delete(key)
    assert not (tmp_path / key).exists()


@pytest.mark.asyncio
async def test_delete_missing_no_error(tmp_path):
    backend = LocalBackend(str(tmp_path))
    # Should not raise even if file doesn't exist
    await backend.delete("nonexistent.png")

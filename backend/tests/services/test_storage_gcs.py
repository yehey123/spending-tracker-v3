import pytest
from unittest.mock import MagicMock, patch

from src.domain.services.storage.gcs import GCSBackend
from src.domain.services.storage.base import StorageError


def _make_backend():
    return GCSBackend(bucket="test-bucket")


def _make_not_found():
    from google.api_core.exceptions import NotFound
    return NotFound("not found")


@pytest.mark.asyncio
async def test_save_calls_upload_from_string():
    backend = _make_backend()
    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs_client = MagicMock()
    mock_gcs_client.bucket.return_value = mock_bucket
    with patch.object(backend, "_client", return_value=mock_gcs_client):
        await backend.save("abc.png", b"data")
    mock_blob.upload_from_string.assert_called_once_with(b"data")


@pytest.mark.asyncio
async def test_save_returns_key():
    backend = _make_backend()
    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs_client = MagicMock()
    mock_gcs_client.bucket.return_value = mock_bucket
    with patch.object(backend, "_client", return_value=mock_gcs_client):
        result = await backend.save("abc.png", b"data")
    assert result == "abc.png"


@pytest.mark.asyncio
async def test_delete_calls_blob_delete():
    backend = _make_backend()
    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs_client = MagicMock()
    mock_gcs_client.bucket.return_value = mock_bucket
    with patch.object(backend, "_client", return_value=mock_gcs_client):
        await backend.delete("abc.png")
    mock_blob.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_not_found_silent():
    backend = _make_backend()
    mock_blob = MagicMock()
    mock_blob.delete.side_effect = _make_not_found()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs_client = MagicMock()
    mock_gcs_client.bucket.return_value = mock_bucket
    with patch.object(backend, "_client", return_value=mock_gcs_client):
        # Should not raise
        await backend.delete("missing.png")


@pytest.mark.asyncio
async def test_save_api_error_raises_storage_error():
    from google.api_core.exceptions import GoogleAPIError
    backend = _make_backend()
    mock_blob = MagicMock()
    mock_blob.upload_from_string.side_effect = GoogleAPIError("denied")
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_gcs_client = MagicMock()
    mock_gcs_client.bucket.return_value = mock_bucket
    with patch.object(backend, "_client", return_value=mock_gcs_client):
        with pytest.raises(StorageError):
            await backend.save("abc.png", b"data")

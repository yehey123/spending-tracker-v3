import pytest
from unittest.mock import MagicMock, patch

from src.domain.services.storage.s3 import S3Backend
from src.domain.services.storage.base import StorageError


def _make_backend():
    return S3Backend(bucket="test-bucket", aws_access_key_id="key", aws_secret_access_key="secret")


def _make_client_error(code: str):
    import botocore.exceptions
    error_response = {"Error": {"Code": code, "Message": "msg"}}
    return botocore.exceptions.ClientError(error_response, "op")


@pytest.mark.asyncio
async def test_save_calls_put_object():
    backend = _make_backend()
    mock_client = MagicMock()
    with patch.object(backend, "_client", return_value=mock_client):
        await backend.save("abc.png", b"data")
    mock_client.put_object.assert_called_once_with(Bucket="test-bucket", Key="abc.png", Body=b"data")


@pytest.mark.asyncio
async def test_save_returns_key():
    backend = _make_backend()
    mock_client = MagicMock()
    with patch.object(backend, "_client", return_value=mock_client):
        result = await backend.save("abc.png", b"data")
    assert result == "abc.png"


@pytest.mark.asyncio
async def test_delete_calls_delete_object():
    backend = _make_backend()
    mock_client = MagicMock()
    with patch.object(backend, "_client", return_value=mock_client):
        await backend.delete("abc.png")
    mock_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="abc.png")


@pytest.mark.asyncio
async def test_delete_not_found_silent():
    backend = _make_backend()
    mock_client = MagicMock()
    mock_client.delete_object.side_effect = _make_client_error("NoSuchKey")
    with patch.object(backend, "_client", return_value=mock_client):
        # Should not raise
        await backend.delete("missing.png")


@pytest.mark.asyncio
async def test_save_client_error_raises_storage_error():
    backend = _make_backend()
    mock_client = MagicMock()
    mock_client.put_object.side_effect = _make_client_error("AccessDenied")
    with patch.object(backend, "_client", return_value=mock_client):
        with pytest.raises(StorageError):
            await backend.save("abc.png", b"data")

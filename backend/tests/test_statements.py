import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image
import io


def _make_png_bytes():
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mock_storage():
    """Return a mock StorageBackend that records calls without touching the filesystem."""
    m = MagicMock()
    m.save = AsyncMock(return_value="test-key.png")
    m.delete = AsyncMock()
    return m


@pytest.mark.asyncio
async def test_upload_statement_image(client):
    png = _make_png_bytes()
    mock_ocr = AsyncMock(return_value="01/05/2026 | GRAB FOOD | 150.00 | DEBIT\n01/05/2026 | SALARY | 50000.00 | CREDIT")
    mock_pre = MagicMock(return_value=Image.new("L", (100, 100)))
    mock_store = _mock_storage()
    with patch("src.api.routes.statements.preprocess", mock_pre), \
         patch("src.api.routes.statements.get_storage_backend", return_value=mock_store), \
         patch("src.api.routes.statements.TesseractProvider") as MockProv:
        instance = MockProv.return_value
        instance.extract_text = mock_ocr
        res = await client.post(
            "/statements/upload",
            files={"file": ("bank.png", png, "image/png")},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "done"
    assert data["transaction_count"] == 2
    assert data["filename"] == "bank.png"
    mock_store.save.assert_called_once()


@pytest.mark.asyncio
async def test_upload_unsupported_type(client):
    res = await client.post(
        "/statements/upload",
        files={"file": ("doc.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 400
    assert "Unsupported" in res.json()["detail"]


@pytest.mark.asyncio
async def test_upload_too_large(client):
    big = b"x" * (21 * 1024 * 1024)
    res = await client.post(
        "/statements/upload",
        files={"file": ("big.png", big, "image/png")},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_list_statements(client):
    png = _make_png_bytes()
    mock_ocr = AsyncMock(return_value="")
    mock_pre = MagicMock(return_value=Image.new("L", (100, 100)))
    mock_store = _mock_storage()
    with patch("src.api.routes.statements.preprocess", mock_pre), \
         patch("src.api.routes.statements.get_storage_backend", return_value=mock_store), \
         patch("src.api.routes.statements.TesseractProvider") as MockProv:
        instance = MockProv.return_value
        instance.extract_text = mock_ocr
        await client.post("/statements/upload", files={"file": ("s.png", png, "image/png")})
    res = await client.get("/statements")
    assert res.status_code == 200
    assert len(res.json()) >= 1


@pytest.mark.asyncio
async def test_delete_statement(client):
    png = _make_png_bytes()
    mock_ocr = AsyncMock(return_value="")
    mock_pre = MagicMock(return_value=Image.new("L", (100, 100)))
    mock_store = _mock_storage()
    with patch("src.api.routes.statements.preprocess", mock_pre), \
         patch("src.api.routes.statements.get_storage_backend", return_value=mock_store), \
         patch("src.api.routes.statements.TesseractProvider") as MockProv:
        instance = MockProv.return_value
        instance.extract_text = mock_ocr
        stmt = (await client.post("/statements/upload", files={"file": ("del.png", png, "image/png")})).json()
    storage_for_delete = _mock_storage()
    with patch("src.api.routes.statements.get_storage_backend", return_value=storage_for_delete):
        res = await client.delete(f"/statements/{stmt['id']}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_delete_calls_storage_with_storage_key(client):
    """Pins the delete-bug fix: delete must use storage_key, not filename."""
    png = _make_png_bytes()
    mock_ocr = AsyncMock(return_value="")
    mock_pre = MagicMock(return_value=Image.new("L", (100, 100)))
    mock_store = _mock_storage()
    with patch("src.api.routes.statements.preprocess", mock_pre), \
         patch("src.api.routes.statements.get_storage_backend", return_value=mock_store), \
         patch("src.api.routes.statements.TesseractProvider") as MockProv:
        instance = MockProv.return_value
        instance.extract_text = mock_ocr
        stmt = (await client.post("/statements/upload", files={"file": ("receipt.png", png, "image/png")})).json()

    # Capture the key that was stored (uuid-based, not the original filename)
    saved_key = mock_store.save.call_args[0][0]  # first positional arg to save()

    storage_for_delete = _mock_storage()
    with patch("src.api.routes.statements.get_storage_backend", return_value=storage_for_delete):
        await client.delete(f"/statements/{stmt['id']}")

    # Delete must be called with the uuid key, not "receipt.png"
    storage_for_delete.delete.assert_called_once_with(saved_key)
    assert saved_key != "receipt.png"

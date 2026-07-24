import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image
import io


def _make_png_bytes():
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_statement_image(client):
    png = _make_png_bytes()
    mock_ocr = AsyncMock(return_value="01/05/2026 | GRAB FOOD | 150.00 | DEBIT\n01/05/2026 | SALARY | 50000.00 | CREDIT")
    mock_pre = MagicMock(return_value=Image.new("L", (100, 100)))
    with patch("src.domain.services.preprocessor.preprocess", mock_pre), \
         patch("src.domain.services.statement_pipeline.TesseractProvider") as MockProv:
        instance = MockProv.return_value
        instance.extract_text = mock_ocr
        res = await client.post(
            "/statements/upload",
            files={"file": ("bank.png", png, "image/png")},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("staged", "committed")
    assert data["transaction_count"] == 2
    assert data["filename"] == "bank.png"


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
    with patch("src.domain.services.preprocessor.preprocess", mock_pre), \
         patch("src.domain.services.statement_pipeline.TesseractProvider") as MockProv:
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
    with patch("src.domain.services.preprocessor.preprocess", mock_pre), \
         patch("src.domain.services.statement_pipeline.TesseractProvider") as MockProv:
        instance = MockProv.return_value
        instance.extract_text = mock_ocr
        stmt = (await client.post("/statements/upload", files={"file": ("del.png", png, "image/png")})).json()
    res = await client.delete(f"/statements/{stmt['id']}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_delete_removes_statement_no_storage(client):
    """Files are processed in memory only — no storage backend is called on upload or delete."""
    png = _make_png_bytes()
    mock_ocr = AsyncMock(return_value="")
    mock_pre = MagicMock(return_value=Image.new("L", (100, 100)))
    with patch("src.domain.services.preprocessor.preprocess", mock_pre), \
         patch("src.domain.services.statement_pipeline.TesseractProvider") as MockProv:
        instance = MockProv.return_value
        instance.extract_text = mock_ocr
        stmt = (await client.post("/statements/upload", files={"file": ("receipt.png", png, "image/png")})).json()

    res = await client.delete(f"/statements/{stmt['id']}")
    assert res.status_code == 204

    remaining = (await client.get("/statements")).json()
    assert stmt["id"] not in [s["id"] for s in remaining]

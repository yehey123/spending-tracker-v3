import io
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image


def _make_png_bytes():
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_upload_statement_image(client):
    png = _make_png_bytes()
    mock_ocr = AsyncMock(
        return_value=(
            "01/05/2026 | GRAB FOOD | 150.00 | DEBIT\n01/05/2026 | SALARY | 50000.00 | CREDIT"
        )
    )
    with patch("src.domain.services.statement_pipeline.TesseractProvider") as MockProv:
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
    with patch("src.domain.services.statement_pipeline.TesseractProvider") as MockProv:
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
    with patch("src.domain.services.statement_pipeline.TesseractProvider") as MockProv:
        instance = MockProv.return_value
        instance.extract_text = mock_ocr
        stmt = (
            await client.post("/statements/upload", files={"file": ("del.png", png, "image/png")})
        ).json()
    res = await client.delete(f"/statements/{stmt['id']}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_delete_removes_statement_no_storage(client):
    """Files are processed in memory only — no storage backend is called on upload or delete."""
    png = _make_png_bytes()
    mock_ocr = AsyncMock(return_value="")
    with patch("src.domain.services.statement_pipeline.TesseractProvider") as MockProv:
        instance = MockProv.return_value
        instance.extract_text = mock_ocr
        stmt = (
            await client.post(
                "/statements/upload", files={"file": ("receipt.png", png, "image/png")}
            )
        ).json()

    res = await client.delete(f"/statements/{stmt['id']}")
    assert res.status_code == 204

    remaining = (await client.get("/statements")).json()
    assert stmt["id"] not in [s["id"] for s in remaining]


@pytest.mark.asyncio
async def test_upload_flush_failure_returns_handled_error(client):
    """A flush IntegrityError must roll back and surface as 'Pipeline error'.

    Without the rollback the route raises PendingRollbackError instead.
    """
    from datetime import datetime
    from decimal import Decimal

    from src.domain.models.transaction import Transaction

    async def failing_run(statement, content, content_type, db, **kwargs):
        # amount 0 violates ck_transactions_amount_positive at flush time
        db.add(
            Transaction(
                date=datetime(2024, 1, 1),
                description="BAD",
                amount=Decimal("0.00"),
                direction="debit",
                statement_id=statement.id,
                status="staged",
                transaction_origin="uploaded",
                user_id=kwargs.get("user_id"),
            )
        )
        await db.flush()

    with patch("src.domain.services.statement_pipeline.statement_pipeline.run", new=failing_run):
        res = await client.post(
            "/statements/upload",
            files={"file": ("bank.png", _make_png_bytes(), "image/png")},
        )
    assert res.status_code == 500
    assert res.json()["detail"].startswith("Pipeline error")


@pytest.mark.asyncio
async def test_upload_skips_non_positive_amount_rows(client):
    mock_ocr = AsyncMock(
        return_value="01/05/2026 | ZERO | 0.00 | DEBIT\n01/05/2026 | GRAB FOOD | 150.00 | DEBIT"
    )
    with patch("src.domain.services.statement_pipeline.TesseractProvider") as MockProv:
        MockProv.return_value.extract_text = mock_ocr
        res = await client.post(
            "/statements/upload", files={"file": ("bank.png", _make_png_bytes(), "image/png")}
        )
    assert res.status_code == 200
    assert res.json()["transaction_count"] == 1

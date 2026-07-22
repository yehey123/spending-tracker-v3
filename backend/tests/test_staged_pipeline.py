"""Tests for E1: staged statement pipeline and TTL cleanup automation."""

import io
import pytest
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image
from sqlalchemy import select

from src.domain.models.statement import Statement
from src.domain.models.transaction import Transaction
from src.tasks.ttl_cleanup import run_ttl_cleanup


def _png():
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mock_storage():
    m = MagicMock()
    m.save = AsyncMock(return_value="test-key.png")
    m.delete = AsyncMock()
    return m


async def _upload(client, ocr_text="01/05/2026 | GRAB FOOD | 150.00 | DEBIT"):
    mock_pre = MagicMock(return_value=Image.new("L", (100, 100)))
    mock_store = _mock_storage()
    with patch("src.domain.services.preprocessor.preprocess", mock_pre), \
         patch("src.api.routes.statements.get_storage_backend", return_value=mock_store), \
         patch("src.domain.services.statement_pipeline.TesseractProvider") as MockProv:
        instance = MockProv.return_value
        instance.extract_text = AsyncMock(return_value=ocr_text)
        res = await client.post(
            "/statements/upload",
            files={"file": ("bank.png", _png(), "image/png")},
        )
    return res.json()


@pytest.mark.asyncio
async def test_staged_pipeline_pauses_at_staged(client):
    await client.put("/settings", json={"ocr_provider": "tesseract", "review_before_commit": True})
    stmt = await _upload(client)
    assert stmt["status"] == "staged"
    txs = (await client.get("/transactions")).json()
    assert len(txs) == 0


@pytest.mark.asyncio
async def test_commit_promotes_transactions(client):
    await client.put("/settings", json={"ocr_provider": "tesseract", "review_before_commit": True})
    stmt = await _upload(client)
    assert stmt["status"] == "staged"
    res = await client.post(f"/statements/{stmt['id']}/commit")
    assert res.status_code == 200
    txs = (await client.get("/transactions")).json()
    assert len(txs) == 1
    assert txs[0]["description"] == "GRAB FOOD"


@pytest.mark.asyncio
async def test_discard_deletes_staged(client):
    await client.put("/settings", json={"ocr_provider": "tesseract", "review_before_commit": True})
    stmt = await _upload(client)
    res = await client.post(f"/statements/{stmt['id']}/discard")
    assert res.status_code == 200
    staged = (await client.get(f"/statements/{stmt['id']}/staged")).json()
    assert staged["transactions"] == []
    txs = (await client.get("/transactions")).json()
    assert len(txs) == 0


@pytest.mark.asyncio
async def test_auto_commit_mode(client):
    await client.put("/settings", json={"ocr_provider": "tesseract", "review_before_commit": False})
    stmt = await _upload(client)
    assert stmt["status"] == "committed"
    txs = (await client.get("/transactions")).json()
    assert len(txs) == 1


@pytest.mark.asyncio
async def test_patch_staged_transaction(client):
    await client.put("/settings", json={"ocr_provider": "tesseract", "review_before_commit": True})
    stmt = await _upload(client)
    staged = (await client.get(f"/statements/{stmt['id']}/staged")).json()
    tx_id = staged["transactions"][0]["id"]

    patch_res = await client.patch(f"/staged-transactions/{tx_id}", json={"amount": "999.00"})
    assert patch_res.status_code == 200

    staged_after = (await client.get(f"/statements/{stmt['id']}/staged")).json()
    assert pytest.approx(float(staged_after["transactions"][0]["amount"]), abs=0.01) == 999.0


@pytest.mark.asyncio
async def test_ttl_cleanup(db_session):
    old_time = datetime.now(timezone.utc) - timedelta(days=8)
    stmt = Statement(
        filename="old.png",
        type="image",
        status="staged",
        ocr_provider="tesseract",
        uploaded_at=old_time,
    )
    db_session.add(stmt)
    await db_session.flush()
    stmt_id = stmt.id

    tx = Transaction(
        statement_id=stmt_id,
        date=datetime(2026, 1, 1),
        amount=100,
        description="Stale tx",
        direction="debit",
        status="staged",
        transaction_origin="upload",
    )
    db_session.add(tx)
    await db_session.commit()
    tx_id = tx.id

    # Patch AsyncSessionLocal so TTL cleanup targets the test DB session
    @asynccontextmanager
    async def _test_session():
        yield db_session

    with patch("src.tasks.ttl_cleanup.AsyncSessionLocal", _test_session):
        await run_ttl_cleanup()

    db_session.expire_all()
    result_stmt = await db_session.execute(select(Statement).where(Statement.id == stmt_id))
    stmt_after = result_stmt.scalar_one()
    status = stmt_after.status.value if hasattr(stmt_after.status, "value") else stmt_after.status
    assert status == "discarded"

    result_tx = await db_session.execute(select(Transaction).where(Transaction.id == tx_id))
    assert result_tx.scalar_one_or_none() is None

"""Tests for receipts linking API."""

import asyncpg
import pytest
from tests.conftest import TEST_DB_RAW


async def _create_receipt_statement(declared_total: str | None = None) -> int:
    """Insert a receipt statement directly via DB."""
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        row = await conn.fetchrow(
            """INSERT INTO statements (filename, storage_key, type, status, ocr_provider, file_type, declared_total)
               VALUES ($1, $2, 'image', 'committed', 'tesseract', 'receipt', $3)
               RETURNING id""",
            "receipt.jpg",
            "receipt-key.jpg",
            declared_total,
        )
        return row["id"]
    finally:
        await conn.close()


async def _create_active_tx(client, amount: str = "50.00", date: str = "2026-05-15T00:00:00") -> dict:
    res = await client.post("/transactions", json={
        "date": date,
        "amount": amount,
        "description": "Receipt match test",
        "direction": "debit",
    })
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.asyncio
async def test_list_receipts_empty(client):
    res = await client.get("/receipts")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_receipts_shows_receipt_statements(client):
    await _create_receipt_statement(declared_total="75.00")
    res = await client.get("/receipts")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["declared_total"] == "75.0000"


@pytest.mark.asyncio
async def test_link_receipt_success(client):
    rid = await _create_receipt_statement(declared_total="50.00")
    tx = await _create_active_tx(client, amount="50.00")

    res = await client.post(f"/receipts/{rid}/link", json={"transaction_id": tx["id"]})
    assert res.status_code == 200
    body = res.json()
    assert body["linked"] == rid
    assert body["transaction_id"] == tx["id"]


@pytest.mark.asyncio
async def test_link_receipt_amount_mismatch(client):
    rid = await _create_receipt_statement(declared_total="50.00")
    tx = await _create_active_tx(client, amount="100.00")

    res = await client.post(f"/receipts/{rid}/link", json={"transaction_id": tx["id"]})
    assert res.status_code == 422
    assert "AMOUNT_MISMATCH" in res.json()["detail"]


@pytest.mark.asyncio
async def test_unlink_receipt(client):
    rid = await _create_receipt_statement(declared_total="50.00")
    tx = await _create_active_tx(client, amount="50.00")

    link_res = await client.post(f"/receipts/{rid}/link", json={"transaction_id": tx["id"]})
    assert link_res.status_code == 200

    unlink_res = await client.post(f"/receipts/{rid}/unlink")
    assert unlink_res.status_code == 200
    assert unlink_res.json()["unlinked"] == rid


@pytest.mark.asyncio
async def test_link_receipt_not_found(client):
    res = await client.post("/receipts/99999/link", json={"transaction_id": 1})
    assert res.status_code == 404

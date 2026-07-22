"""Tests for E2a: reversal + correction ledger model semantics."""

import pytest
from datetime import datetime

from sqlalchemy import select

from src.domain.models.statement import Statement
from src.domain.models.transaction import Transaction


async def _make_tx(client, **kwargs):
    defaults = {
        "date": "2026-05-10T00:00:00",
        "amount": "100.00",
        "description": "Test tx",
        "direction": "debit",
    }
    defaults.update(kwargs)
    return (await client.post("/transactions", json=defaults)).json()


@pytest.mark.asyncio
async def test_patch_financial_field_creates_reversal_pair(client):
    tx = await _make_tx(client)
    res = await client.patch(f"/transactions/{tx['id']}", json={"amount": 200.00})
    assert res.status_code == 200
    data = res.json()
    assert data["reversal_id"] is not None
    assert data["correction_id"] is not None

    txs = (await client.get("/transactions")).json()
    ids = [t["id"] for t in txs]
    assert tx["id"] not in ids
    assert data["correction_id"] in ids


@pytest.mark.asyncio
async def test_patch_category_direct_update_with_audit_log(client):
    tx = await _make_tx(client)
    cat = (await client.post("/categories", json={"name": "Food", "color": "#f97316"})).json()
    res = await client.patch(f"/transactions/{tx['id']}", json={"category_id": cat["id"]})
    assert res.status_code == 200
    data = res.json()
    assert data.get("reversal_id") is None
    assert data.get("correction_id") is None

    history = (await client.get(f"/transactions/{tx['id']}/history")).json()
    assert any(e["field"] == "category_id" for e in history)


@pytest.mark.asyncio
async def test_reverse_transaction(client):
    tx = await _make_tx(client)
    res = await client.post(f"/transactions/{tx['id']}/reverse", json={"reason": "duplicate"})
    assert res.status_code == 200
    data = res.json()
    assert data["original_id"] == tx["id"]
    assert data["reason"] == "duplicate"
    assert "reversal_id" in data


@pytest.mark.asyncio
async def test_reverse_already_reversed_409(client):
    tx = await _make_tx(client)
    await client.post(f"/transactions/{tx['id']}/reverse", json={"reason": "duplicate"})
    res = await client.post(f"/transactions/{tx['id']}/reverse", json={"reason": "duplicate"})
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_reversed_rows_excluded_from_list(client):
    tx = await _make_tx(client)
    res = await client.post(f"/transactions/{tx['id']}/reverse", json={"reason": "user_error"})
    assert res.status_code == 200
    txs = (await client.get("/transactions")).json()
    assert tx["id"] not in [t["id"] for t in txs]


@pytest.mark.asyncio
async def test_staged_patch_is_direct_no_reversal(client, db_session):
    stmt = Statement(
        filename="test.png",
        type="image",
        status="staged",
        ocr_provider="tesseract",
        uploaded_at=datetime.now(),
    )
    db_session.add(stmt)
    await db_session.flush()

    tx = Transaction(
        statement_id=stmt.id,
        date=datetime(2026, 5, 10),
        amount=100,
        description="Staged tx",
        direction="debit",
        status="staged",
        transaction_origin="upload",
    )
    db_session.add(tx)
    await db_session.commit()

    res = await client.patch(f"/staged-transactions/{tx.id}", json={"amount": "250.00"})
    assert res.status_code == 200

    result = await db_session.execute(
        select(Transaction).where(Transaction.reversal_of == tx.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_correction_row_appears_in_analytics(client):
    now = datetime.now()
    month = f"{now.year}-{now.month:02d}"

    tx = await _make_tx(
        client,
        date=f"{now.year}-{now.month:02d}-10T00:00:00",
        amount="100.00",
        direction="debit",
    )
    await client.patch(f"/transactions/{tx['id']}", json={"amount": 200.00})

    res = await client.get(f"/analytics/by-category?month={month}")
    assert res.status_code == 200
    total = float(res.json()["total_debit"])
    assert pytest.approx(total, abs=0.01) == 200.0

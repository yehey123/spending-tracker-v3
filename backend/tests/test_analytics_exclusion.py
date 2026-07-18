"""Wave 0B: verify analytics endpoints exclude reversed/staged transactions."""

import asyncpg
import pytest
from tests.conftest import TEST_DB_RAW


async def _create_tx(client, *, month: str, amount: str, direction: str = "debit",
                     category_id: int | None = None) -> int:
    resp = await client.post("/transactions", json={
        "date": f"{month}-01T00:00:00",
        "amount": amount,
        "description": "Test transaction",
        "direction": direction,
        "category_id": category_id,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _set_reversed_pair(tx_id: int, reverse_tx_id: int):
    """Mark tx_id as reversed-by reverse_tx_id and vice versa via direct DB write."""
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        await conn.execute(
            "UPDATE transactions SET reversed_by = $1 WHERE id = $2",
            reverse_tx_id, tx_id
        )
        await conn.execute(
            "UPDATE transactions SET reversal_of = $1 WHERE id = $2",
            tx_id, reverse_tx_id
        )
    finally:
        await conn.close()


async def _set_status(tx_id: int, status: str):
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        await conn.execute("UPDATE transactions SET status = $1 WHERE id = $2", status, tx_id)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_by_category_excludes_reversed(client):
    """A reversed pair must not appear in by-category totals."""
    cat = (await client.post("/categories", json={"name": "Food", "color": "#FF0000"})).json()
    month = "2026-07"

    # Active transaction — should appear
    active_id = await _create_tx(client, month=month, amount="100.00",
                                  category_id=cat["id"])
    # Reversed pair — neither should appear
    orig_id = await _create_tx(client, month=month, amount="200.00",
                                category_id=cat["id"])
    rev_id = await _create_tx(client, month=month, amount="200.00",
                               category_id=cat["id"])
    await _set_reversed_pair(orig_id, rev_id)

    res = await client.get(f"/analytics/by-category?month={month}")
    assert res.status_code == 200
    data = res.json()
    # Only the 100.00 active transaction should count
    assert float(data["total_debit"]) == pytest.approx(100.0)
    food = next((b for b in data["breakdown"] if b["category_id"] == cat["id"]), None)
    assert food is not None
    assert float(food["amount"]) == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_by_category_excludes_staged(client):
    """Staged (non-active) transactions must not appear in by-category totals."""
    cat = (await client.post("/categories", json={"name": "Bills", "color": "#0000FF"})).json()
    month = "2026-07"

    active_id = await _create_tx(client, month=month, amount="50.00",
                                  category_id=cat["id"])
    staged_id = await _create_tx(client, month=month, amount="999.00",
                                  category_id=cat["id"])
    await _set_status(staged_id, "staged")

    res = await client.get(f"/analytics/by-category?month={month}")
    assert res.status_code == 200
    data = res.json()
    assert float(data["total_debit"]) == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_cash_flow_excludes_reversed(client):
    """A reversed credit must not appear in cash-flow totals."""
    month = "2026-07"

    active_id = await _create_tx(client, month=month, amount="1000.00", direction="credit")
    orig_id = await _create_tx(client, month=month, amount="500.00", direction="credit")
    rev_id = await _create_tx(client, month=month, amount="500.00", direction="credit")
    await _set_reversed_pair(orig_id, rev_id)

    res = await client.get("/analytics/cash-flow?months=12")
    assert res.status_code == 200
    data = res.json()
    jul = next((m for m in data["months"] if m["month"] == month), None)
    assert jul is not None
    # Only the 1000.00 active credit should count
    assert float(jul["total_credit"]) == pytest.approx(1000.0)


@pytest.mark.asyncio
async def test_cash_flow_excludes_staged(client):
    """Staged transactions must not appear in cash-flow totals."""
    month = "2026-07"

    active_id = await _create_tx(client, month=month, amount="300.00", direction="debit")
    staged_id = await _create_tx(client, month=month, amount="700.00", direction="debit")
    await _set_status(staged_id, "staged")

    res = await client.get("/analytics/cash-flow?months=12")
    assert res.status_code == 200
    data = res.json()
    jul = next((m for m in data["months"] if m["month"] == month), None)
    assert jul is not None
    assert float(jul["total_debit"]) == pytest.approx(300.0)

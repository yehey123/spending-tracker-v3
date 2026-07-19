import base64
import json

import asyncpg
import pytest
from tests.conftest import TEST_DB_RAW


async def _set_reversed_by(tx_id: int, reverse_tx_id: int):
    """Mark tx as reversed via direct DB write (avoids reversal endpoint timezone bug)."""
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        await conn.execute("UPDATE transactions SET reversed_by = $1 WHERE id = $2", reverse_tx_id, tx_id)
        await conn.execute("UPDATE transactions SET reversal_of = $1 WHERE id = $2", tx_id, reverse_tx_id)
    finally:
        await conn.close()


async def _make_tx(client, description: str, amount: str = "50.00", date: str = "2026-05-15T00:00:00"):
    res = await client.post("/transactions", json={
        "date": date,
        "amount": amount,
        "description": description,
        "direction": "debit",
    })
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.asyncio
async def test_search_matches_description(client):
    await _make_tx(client, "Coffee Shop Visit")
    await _make_tx(client, "Coffee Beans Online")
    await _make_tx(client, "Monthly Salary")

    res = await client.get("/transactions/search?q=coffee")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    descriptions = {tx["description"] for tx in data}
    assert "Coffee Shop Visit" in descriptions
    assert "Coffee Beans Online" in descriptions


@pytest.mark.asyncio
async def test_search_limit(client):
    await _make_tx(client, "Coffee Shop Visit", date="2026-05-15T00:00:00")
    await _make_tx(client, "Coffee Beans Online", date="2026-05-14T00:00:00")

    res = await client.get("/transactions/search?q=coffee&limit=1")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1


@pytest.mark.asyncio
async def test_search_cursor_pagination(client):
    tx1 = await _make_tx(client, "Coffee Shop Visit", date="2026-05-15T00:00:00")
    tx2 = await _make_tx(client, "Coffee Beans Online", date="2026-05-14T00:00:00")

    # First page
    res1 = await client.get("/transactions/search?q=coffee&limit=1")
    assert res1.status_code == 200
    page1 = res1.json()
    assert len(page1) == 1
    first_id = page1[0]["id"]

    # Build cursor from first result
    cursor_payload = json.dumps({"date": page1[0]["date"], "id": page1[0]["id"]})
    cursor = base64.b64encode(cursor_payload.encode()).decode()

    # Second page
    res2 = await client.get(f"/transactions/search?q=coffee&limit=1&cursor={cursor}")
    assert res2.status_code == 200
    page2 = res2.json()
    assert len(page2) == 1
    assert page2[0]["id"] != first_id


@pytest.mark.asyncio
async def test_search_excludes_reversed(client):
    tx1 = await _make_tx(client, "CoffeeReversedXYZ", date="2026-05-15T00:00:00")
    tx2 = await _make_tx(client, "CoffeeReversedXYZ reversal", date="2026-05-14T00:00:00")
    # Mark tx1 as reversed via direct DB write (reversal endpoint has timezone bug)
    await _set_reversed_by(tx1["id"], tx2["id"])

    res = await client.get("/transactions/search?q=CoffeeReversedXYZ")
    assert res.status_code == 200
    data = res.json()
    ids = {item["id"] for item in data}
    assert tx1["id"] not in ids


@pytest.mark.asyncio
async def test_search_invalid_cursor(client):
    res = await client.get("/transactions/search?q=coffee&cursor=notvalidbase64!!!")
    assert res.status_code == 400

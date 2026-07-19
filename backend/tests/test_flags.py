"""Tests for the flags API endpoints.

Acceptance criteria:
1. GET /flags returns list of open flags
2. GET /flags/count returns {"count": N} for open flags
3. PATCH /flags/{id} with {status: "confirmed"} → transaction's category_id is updated;
   flag status becomes "confirmed"
4. After confirm, GET /flags/count returns {"count": 0}
5. PATCH /flags/{id} with {status: "rejected"} → flag resolved, category unchanged
6. PATCH /flags/{id} with invalid status → 422
"""

import asyncpg
import pytest

from tests.conftest import TEST_DB_RAW


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _make_category(client, name="Misc", color="#123456"):
    return (await client.post("/categories", json={"name": name, "color": color})).json()


async def _make_tx(client, description="Coffee Shop"):
    res = await client.post("/transactions", json={
        "date": "2026-05-15T00:00:00",
        "amount": "50.00",
        "description": description,
        "direction": "debit",
    })
    assert res.status_code == 201
    return res.json()


async def _create_flag(tx_id: int, cat_id: int) -> int:
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        row = await conn.fetchrow(
            """INSERT INTO transaction_flags (transaction_id, flag_type, status, metadata)
               VALUES ($1, 'category_suggestion', 'open', $2::jsonb) RETURNING id""",
            tx_id,
            f'{{"suggested_category_id": {cat_id}, "confidence": 0.9, "merchant_key": "coffee shop"}}',
        )
        return row["id"]
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_flags_empty(client):
    """GET /flags with no flags returns empty list."""
    res = await client.get("/flags")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_get_flags_returns_open_flags(client):
    """GET /flags returns the open flag we created (AC-1)."""
    cat = await _make_category(client, name="Food")
    tx = await _make_tx(client)
    flag_id = await _create_flag(tx["id"], cat["id"])

    res = await client.get("/flags")
    assert res.status_code == 200

    flags = res.json()
    assert isinstance(flags, list)
    assert len(flags) == 1

    flag = flags[0]
    assert flag["id"] == flag_id
    assert flag["transaction_id"] == tx["id"]
    assert flag["flag_type"] == "category_suggestion"
    assert flag["status"] == "open"


@pytest.mark.asyncio
async def test_get_flags_returns_multiple_open_flags(client):
    """GET /flags returns all open flags when multiple exist."""
    cat = await _make_category(client, name="Transport")
    tx1 = await _make_tx(client, description="Ride 1")
    tx2 = await _make_tx(client, description="Ride 2")
    await _create_flag(tx1["id"], cat["id"])
    await _create_flag(tx2["id"], cat["id"])

    res = await client.get("/flags")
    assert res.status_code == 200
    assert len(res.json()) == 2


@pytest.mark.asyncio
async def test_get_flags_count_with_open_flags(client):
    """GET /flags/count returns {"count": N} for open flags (AC-2)."""
    cat = await _make_category(client, name="Groceries")
    tx1 = await _make_tx(client, description="Market 1")
    tx2 = await _make_tx(client, description="Market 2")
    await _create_flag(tx1["id"], cat["id"])
    await _create_flag(tx2["id"], cat["id"])

    res = await client.get("/flags/count")
    assert res.status_code == 200

    data = res.json()
    assert "count" in data
    assert data["count"] == 2


@pytest.mark.asyncio
async def test_get_flags_count_empty(client):
    """GET /flags/count returns {"count": 0} when no open flags."""
    res = await client.get("/flags/count")
    assert res.status_code == 200
    assert res.json() == {"count": 0}


@pytest.mark.asyncio
async def test_patch_flag_confirm_updates_category(client):
    """PATCH /flags/{id} confirmed → transaction's category_id is updated (AC-3)."""
    cat = await _make_category(client, name="Dining")
    tx = await _make_tx(client)
    # transaction starts with no category
    assert tx["category_id"] is None

    flag_id = await _create_flag(tx["id"], cat["id"])

    res = await client.patch(f"/flags/{flag_id}", json={"status": "confirmed"})
    assert res.status_code == 200

    body = res.json()
    assert body["id"] == flag_id
    assert body["status"] == "confirmed"

    # Verify transaction's category_id was updated to the suggested category
    tx_list = await client.get("/transactions")
    updated_tx = next(t for t in tx_list.json() if t["id"] == tx["id"])
    assert updated_tx["category_id"] == cat["id"]


@pytest.mark.asyncio
async def test_patch_flag_confirm_count_becomes_zero(client):
    """After confirming the only flag, GET /flags/count returns {"count": 0} (AC-4)."""
    cat = await _make_category(client, name="Entertainment")
    tx = await _make_tx(client)
    flag_id = await _create_flag(tx["id"], cat["id"])

    # Confirm the flag
    res = await client.patch(f"/flags/{flag_id}", json={"status": "confirmed"})
    assert res.status_code == 200

    # Count must now be 0
    count_res = await client.get("/flags/count")
    assert count_res.status_code == 200
    assert count_res.json() == {"count": 0}


@pytest.mark.asyncio
async def test_patch_flag_rejected_does_not_change_category(client):
    """PATCH /flags/{id} rejected → flag resolved, category_id unchanged (AC-5)."""
    cat = await _make_category(client, name="Shopping")
    tx = await _make_tx(client)
    assert tx["category_id"] is None

    flag_id = await _create_flag(tx["id"], cat["id"])

    res = await client.patch(f"/flags/{flag_id}", json={"status": "rejected"})
    assert res.status_code == 200

    body = res.json()
    assert body["id"] == flag_id
    assert body["status"] == "rejected"

    # category_id must remain None — not updated to suggested category
    tx_list = await client.get("/transactions")
    unchanged_tx = next(t for t in tx_list.json() if t["id"] == tx["id"])
    assert unchanged_tx["category_id"] is None


@pytest.mark.asyncio
async def test_patch_flag_rejected_flag_not_in_open_list(client):
    """After rejection, GET /flags should not include the resolved flag."""
    cat = await _make_category(client, name="Bills")
    tx = await _make_tx(client)
    flag_id = await _create_flag(tx["id"], cat["id"])

    await client.patch(f"/flags/{flag_id}", json={"status": "rejected"})

    res = await client.get("/flags")
    assert res.status_code == 200
    flag_ids = [f["id"] for f in res.json()]
    assert flag_id not in flag_ids


@pytest.mark.asyncio
async def test_patch_flag_invalid_status_returns_422(client):
    """PATCH /flags/{id} with invalid status → 422 (AC-6)."""
    cat = await _make_category(client, name="Utilities")
    tx = await _make_tx(client)
    flag_id = await _create_flag(tx["id"], cat["id"])

    res = await client.patch(f"/flags/{flag_id}", json={"status": "bogus"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patch_flag_not_found_returns_404(client):
    """PATCH /flags/{id} for a non-existent flag → 404."""
    res = await client.patch("/flags/99999", json={"status": "confirmed"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_patch_flag_already_resolved_returns_409(client):
    """PATCH /flags/{id} on an already-resolved flag → 409."""
    cat = await _make_category(client, name="Health")
    tx = await _make_tx(client)
    flag_id = await _create_flag(tx["id"], cat["id"])

    # Resolve it once
    await client.patch(f"/flags/{flag_id}", json={"status": "confirmed"})

    # Attempt to resolve again
    res = await client.patch(f"/flags/{flag_id}", json={"status": "rejected"})
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_get_flags_flag_metadata_present(client):
    """GET /flags includes flag_metadata with suggested_category_id."""
    cat = await _make_category(client, name="Coffee")
    tx = await _make_tx(client)
    flag_id = await _create_flag(tx["id"], cat["id"])

    res = await client.get("/flags")
    assert res.status_code == 200

    flags = res.json()
    assert len(flags) == 1
    flag = flags[0]
    assert flag["flag_metadata"] is not None
    assert flag["flag_metadata"]["suggested_category_id"] == cat["id"]
    assert flag["flag_metadata"]["confidence"] == 0.9
    assert flag["flag_metadata"]["merchant_key"] == "coffee shop"

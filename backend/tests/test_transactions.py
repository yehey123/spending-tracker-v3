import pytest


async def _make_category(client, name="Misc", color="#123456"):
    return (await client.post("/categories", json={"name": name, "color": color})).json()


@pytest.mark.asyncio
async def test_create_transaction(client):
    res = await client.post("/transactions", json={
        "date": "2026-05-15T00:00:00",
        "amount": "120.50",
        "description": "Grab Food",
        "direction": "debit",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["amount"] == "120.5"
    assert data["direction"] == "debit"
    assert data["category_id"] is None


@pytest.mark.asyncio
async def test_create_transaction_with_category(client):
    cat = await _make_category(client)
    res = await client.post("/transactions", json={
        "date": "2026-05-15T00:00:00",
        "amount": "50.00",
        "description": "Lunch",
        "direction": "debit",
        "category_id": cat["id"],
    })
    assert res.status_code == 201
    assert res.json()["category_id"] == cat["id"]


@pytest.mark.asyncio
async def test_create_transaction_invalid_category(client):
    res = await client.post("/transactions", json={
        "date": "2026-05-15T00:00:00",
        "amount": "50.00",
        "description": "Lunch",
        "direction": "debit",
        "category_id": 9999,
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_list_transactions_filter_month(client):
    await client.post("/transactions", json={
        "date": "2026-04-01T00:00:00", "amount": "10.00",
        "description": "April tx", "direction": "debit",
    })
    await client.post("/transactions", json={
        "date": "2026-05-01T00:00:00", "amount": "20.00",
        "description": "May tx", "direction": "debit",
    })
    res = await client.get("/transactions?month=2026-05")
    data = res.json()
    assert len(data) == 1
    assert data[0]["description"] == "May tx"


@pytest.mark.asyncio
async def test_list_transactions_filter_direction(client):
    await client.post("/transactions", json={
        "date": "2026-05-01T00:00:00", "amount": "100.00",
        "description": "Salary", "direction": "credit",
    })
    await client.post("/transactions", json={
        "date": "2026-05-02T00:00:00", "amount": "20.00",
        "description": "Coffee", "direction": "debit",
    })
    res = await client.get("/transactions?direction=credit")
    data = res.json()
    assert all(t["direction"] == "credit" for t in data)


@pytest.mark.asyncio
async def test_patch_transaction_category(client):
    cat = await _make_category(client)
    tx = (await client.post("/transactions", json={
        "date": "2026-05-10T00:00:00", "amount": "30.00",
        "description": "Item", "direction": "debit",
    })).json()
    res = await client.patch(f"/transactions/{tx['id']}", json={"category_id": cat["id"]})
    assert res.status_code == 200
    assert "id" in res.json()  # returns TransactionPatchResult, not TransactionOut
    # Verify the category was actually applied
    get_res = await client.get("/transactions")
    updated = next(t for t in get_res.json() if t["id"] == tx["id"])
    assert updated["category_id"] == cat["id"]


@pytest.mark.asyncio
async def test_delete_transaction(client):
    tx = (await client.post("/transactions", json={
        "date": "2026-05-10T00:00:00", "amount": "30.00",
        "description": "ToDelete", "direction": "debit",
    })).json()
    res = await client.delete(f"/transactions/{tx['id']}")
    assert res.status_code == 405  # DELETE removed — use POST /transactions/{id}/reverse instead

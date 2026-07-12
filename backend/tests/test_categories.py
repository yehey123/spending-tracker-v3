import pytest


@pytest.mark.asyncio
async def test_get_categories_empty(client):
    res = await client.get("/categories")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_post_category_valid(client):
    res = await client.post("/categories", json={"name": "Food", "color": "#FF5733"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Food"
    assert data["color"] == "#FF5733"
    assert "id" in data


@pytest.mark.asyncio
async def test_post_category_invalid_color(client):
    res = await client.post("/categories", json={"name": "Food", "color": "red"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_post_category_duplicate_case_insensitive(client):
    await client.post("/categories", json={"name": "Food", "color": "#FF5733"})
    res = await client.post("/categories", json={"name": "food", "color": "#FF5733"})
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_put_category(client):
    create = await client.post("/categories", json={"name": "Transport", "color": "#0000FF"})
    cat_id = create.json()["id"]
    res = await client.put(f"/categories/{cat_id}", json={"name": "Travel", "color": "#0000AA"})
    assert res.status_code == 200
    assert res.json()["name"] == "Travel"


@pytest.mark.asyncio
async def test_put_category_not_found(client):
    res = await client.put("/categories/9999", json={"name": "X", "color": "#000000"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_category(client):
    create = await client.post("/categories", json={"name": "ToDelete", "color": "#123456"})
    cat_id = create.json()["id"]
    res = await client.delete(f"/categories/{cat_id}")
    assert res.status_code == 204
    get = await client.get("/categories")
    assert all(c["id"] != cat_id for c in get.json())


@pytest.mark.asyncio
async def test_delete_category_nulls_transactions(client):
    cat = (await client.post("/categories", json={"name": "Nullify", "color": "#AABBCC"})).json()
    tx = (await client.post("/transactions", json={
        "date": "2026-05-01T00:00:00",
        "amount": "50.00",
        "description": "Test",
        "direction": "debit",
        "category_id": cat["id"],
    })).json()
    await client.delete(f"/categories/{cat['id']}")
    tx_get = await client.get(f"/transactions?limit=50")
    found = next(t for t in tx_get.json() if t["id"] == tx["id"])
    assert found["category_id"] is None

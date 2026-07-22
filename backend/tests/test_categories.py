"""Tests for E5: category hierarchy, seed, and deletion rules."""

import pytest
from sqlalchemy import func, select

from src.domain.models.category import Category
from src.domain.services.category_seeder import DEFAULTS, seed_default_categories


@pytest.mark.asyncio
async def test_seed_creates_defaults_on_startup(db_session):
    await seed_default_categories(db_session)
    result = await db_session.execute(select(func.count()).select_from(Category))
    count = result.scalar()
    expected = len(DEFAULTS) + sum(len(children) for _, _, _, children in DEFAULTS)
    assert count == expected


@pytest.mark.asyncio
async def test_seed_is_idempotent(db_session):
    await seed_default_categories(db_session)
    await seed_default_categories(db_session)
    result = await db_session.execute(select(func.count()).select_from(Category))
    count = result.scalar()
    expected = len(DEFAULTS) + sum(len(children) for _, _, _, children in DEFAULTS)
    assert count == expected


@pytest.mark.asyncio
async def test_create_subcategory(client):
    parent = (await client.post("/categories", json={"name": "Transport", "color": "#3b82f6"})).json()
    sub = (await client.post("/categories", json={
        "name": "Ride Hailing",
        "color": "#60a5fa",
        "parent_id": parent["id"],
    })).json()
    assert sub["parent_id"] == parent["id"]
    assert sub["id"] != parent["id"]


@pytest.mark.asyncio
async def test_depth_guard_rejects_three_levels(client):
    parent = (await client.post("/categories", json={"name": "Food", "color": "#f97316"})).json()
    child = (await client.post("/categories", json={
        "name": "Fast Food", "color": "#fbbf24", "parent_id": parent["id"],
    })).json()
    res = await client.post("/categories", json={
        "name": "Burger Joint", "color": "#ff0000", "parent_id": child["id"],
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_delete_parent_with_children_422(client):
    parent = (await client.post("/categories", json={"name": "Bills", "color": "#14b8a6"})).json()
    await client.post("/categories", json={
        "name": "Internet", "color": "#2dd4bf", "parent_id": parent["id"],
    })
    res = await client.delete(f"/categories/{parent['id']}")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_delete_cascades_null_on_transactions(client):
    cat = (await client.post("/categories", json={"name": "Misc", "color": "#aaaaaa"})).json()
    tx = (await client.post("/transactions", json={
        "date": "2026-05-10T00:00:00",
        "amount": "50.00",
        "description": "Misc purchase",
        "direction": "debit",
        "category_id": cat["id"],
    })).json()
    await client.delete(f"/categories/{cat['id']}")
    txs = (await client.get("/transactions")).json()
    updated = next(t for t in txs if t["id"] == tx["id"])
    assert updated["category_id"] is None


@pytest.mark.asyncio
async def test_get_categories_returns_tree(client):
    parent = (await client.post("/categories", json={"name": "Shopping", "color": "#ec4899"})).json()
    await client.post("/categories", json={
        "name": "Online Shopping", "color": "#f472b6", "parent_id": parent["id"],
    })
    res = await client.get("/categories")
    assert res.status_code == 200
    categories = res.json()
    shop = next((c for c in categories if c["name"] == "Shopping"), None)
    assert shop is not None
    assert len(shop["children"]) == 1
    assert shop["children"][0]["name"] == "Online Shopping"

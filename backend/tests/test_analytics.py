import pytest

from src.core.currencies import SUPPORTED_CURRENCIES


async def _seed(client, month="2026-05", n_debit=2, n_credit=1):
    cat = (await client.post("/categories", json={"name": "Food", "color": "#FF0000"})).json()
    for i in range(n_debit):
        await client.post("/transactions", json={
            "date": f"{month}-0{i+1}T00:00:00",
            "amount": "100.00",
            "description": f"Expense {i}",
            "direction": "debit",
            "category_id": cat["id"],
        })
    for i in range(n_credit):
        await client.post("/transactions", json={
            "date": f"{month}-0{i+1}T00:00:00",
            "amount": "5000.00",
            "description": "Salary",
            "direction": "credit",
        })
    return cat


@pytest.mark.asyncio
async def test_by_category(client):
    cat = await _seed(client, month="2026-06", n_debit=2, n_credit=0)
    res = await client.get("/analytics/by-category?month=2026-06")
    assert res.status_code == 200
    data = res.json()
    assert data["month"] == "2026-06"
    assert float(data["total_debit"]) == pytest.approx(200.0)
    assert len(data["breakdown"]) >= 1
    food = next(b for b in data["breakdown"] if b["category_id"] == cat["id"])
    assert float(food["amount"]) == pytest.approx(200.0)
    assert food["percent"] == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_cash_flow(client):
    await _seed(client, month="2026-05", n_debit=1, n_credit=1)
    res = await client.get("/analytics/cash-flow?months=6")
    assert res.status_code == 200
    data = res.json()
    assert "months" in data
    assert len(data["months"]) > 0
    may = next((m for m in data["months"] if m["month"] == "2026-05"), None)
    assert may is not None
    assert float(may["total_debit"]) == pytest.approx(100.0)
    assert float(may["total_credit"]) == pytest.approx(5000.0)


# --- currency allowlist ---

@pytest.mark.asyncio
async def test_by_category_rejects_unknown_currency(client):
    res = await client.get("/analytics/by-category?month=2026-06&display_currency=FAKE")
    assert res.status_code == 422
    assert "Unsupported currency" in res.json()["detail"]


@pytest.mark.asyncio
async def test_cash_flow_rejects_unknown_currency(client):
    res = await client.get("/analytics/cash-flow?months=3&display_currency=BOGUS")
    assert res.status_code == 422
    assert "Unsupported currency" in res.json()["detail"]


@pytest.mark.asyncio
async def test_by_category_accepts_valid_currency(client):
    res = await client.get("/analytics/by-category?month=2026-06&display_currency=USD")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_cash_flow_accepts_valid_currency(client):
    res = await client.get("/analytics/cash-flow?months=3&display_currency=EUR")
    assert res.status_code == 200


def test_supported_currencies_contains_expected():
    # Smoke-check the constant itself — catches accidental truncation.
    assert "USD" in SUPPORTED_CURRENCIES
    assert "EUR" in SUPPORTED_CURRENCIES
    assert "PHP" in SUPPORTED_CURRENCIES
    assert len(SUPPORTED_CURRENCIES) >= 30

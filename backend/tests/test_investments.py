"""Tests for investment transactions and portfolio routes."""

import asyncpg
import pytest
from datetime import date
from tests.conftest import TEST_DB_RAW


async def _create_broker_account() -> int:
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        row = await conn.fetchrow(
            """INSERT INTO accounts (name, type, currency, opening_balance, opening_date)
               VALUES ('Fidelity', 'broker', 'USD', 0, $1) RETURNING id""",
            date(2024, 1, 1),
        )
        return row["id"]
    finally:
        await conn.close()


async def _insert_investment_tx(
    account_id: int,
    symbol: str = "AAPL",
    direction: str = "buy",
    shares: str = "10.000000",
    price: str = "182.500000",
    amount: str = "1825.00",
) -> int:
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        row = await conn.fetchrow(
            """INSERT INTO investment_transactions
               (account_id, date, symbol, direction, shares, price_per_share, amount, currency)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 'USD') RETURNING id""",
            account_id, date(2025, 6, 15), symbol, direction, shares, price, amount,
        )
        return row["id"]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_list_investment_transactions_empty(client):
    acc_id = await _create_broker_account()
    resp = await client.get(f"/accounts/{acc_id}/investment-transactions")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_investment_transactions(client):
    acc_id = await _create_broker_account()
    await _insert_investment_tx(acc_id, symbol="AAPL", direction="buy")
    await _insert_investment_tx(acc_id, symbol="MSFT", direction="buy",
                                shares="5.000000", price="300.000000", amount="1500.00")

    resp = await client.get(f"/accounts/{acc_id}/investment-transactions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    symbols = {t["symbol"] for t in data}
    assert symbols == {"AAPL", "MSFT"}


@pytest.mark.asyncio
async def test_investment_tx_on_non_broker_returns_422(client):
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        row = await conn.fetchrow(
            """INSERT INTO accounts (name, type, currency, opening_balance, opening_date)
               VALUES ('BPI', 'checking', 'PHP', 0, $1) RETURNING id""",
            date(2024, 1, 1),
        )
        acc_id = row["id"]
    finally:
        await conn.close()
    resp = await client.get(f"/accounts/{acc_id}/investment-transactions")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_portfolio_net_shares(client):
    acc_id = await _create_broker_account()
    # Buy 10, sell 3 → net 7
    await _insert_investment_tx(acc_id, "AAPL", "buy", "10.000000", "182.500000", "1825.00")
    await _insert_investment_tx(acc_id, "AAPL", "sell", "3.000000", "200.000000", "600.00")

    resp = await client.get(f"/accounts/{acc_id}/portfolio")
    assert resp.status_code == 200
    holdings = resp.json()["holdings"]
    assert len(holdings) == 1
    assert holdings[0]["symbol"] == "AAPL"
    assert float(holdings[0]["shares_held"]) == pytest.approx(7.0)


@pytest.mark.asyncio
async def test_portfolio_hides_closed_by_default(client):
    acc_id = await _create_broker_account()
    # Buy 5, sell 5 → net 0 (closed)
    await _insert_investment_tx(acc_id, "TSLA", "buy", "5.000000", "250.000000", "1250.00")
    await _insert_investment_tx(acc_id, "TSLA", "sell", "5.000000", "250.000000", "1250.00")

    resp = await client.get(f"/accounts/{acc_id}/portfolio")
    assert resp.status_code == 200
    assert resp.json()["holdings"] == []

    resp2 = await client.get(f"/accounts/{acc_id}/portfolio?include_closed=true")
    assert len(resp2.json()["holdings"]) == 1


@pytest.mark.asyncio
async def test_investment_parser_unit():
    from src.domain.services.investment_parser import parse_investment_rows
    text = "AAPL BUY 10 $182.50\nMSFT sell 5 $300.00"
    rows, errors = parse_investment_rows(text)
    assert len(rows) == 2
    assert errors == []
    assert rows[0].symbol == "AAPL"
    assert rows[0].direction == "buy"
    assert rows[1].direction == "sell"

"""Tests for accounts API — CRUD, fingerprinting, balance computation."""

import asyncpg
import pytest
from tests.conftest import TEST_DB_RAW


async def _create_account_direct(
    name: str = "Test Bank",
    type: str = "checking",
    opening_balance: str = "1000.00",
) -> int:
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        row = await conn.fetchrow(
            """INSERT INTO accounts (name, type, currency, opening_balance)
               VALUES ($1, $2, 'PHP', $3) RETURNING id""",
            name, type, opening_balance,
        )
        return row["id"]
    finally:
        await conn.close()


async def _create_tx_for_account(account_id: int, amount: str, direction: str) -> None:
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        await conn.execute(
            """INSERT INTO transactions
               (date, amount, description, direction, account_id, status)
               VALUES ('2026-06-15', $1, 'Test tx', $2, $3, 'active')""",
            amount, direction, account_id,
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_list_accounts_empty(client):
    resp = await client.get("/accounts")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_account_minimal(client):
    resp = await client.post("/accounts", json={
        "name": "BPI Savings",
        "type": "savings",

    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "BPI Savings"
    assert data["type"] == "savings"
    assert data.get("fingerprint") is None


@pytest.mark.asyncio
async def test_create_account_invalid_type(client):
    resp = await client.post("/accounts", json={
        "name": "Bad",
        "type": "crypto",

    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_account_with_number_stores_last_four(client):
    resp = await client.post("/accounts", json={
        "name": "BPI CC",
        "type": "credit_card",

        "account_number": "4111111111111111",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["last_four"] == "1111"
    assert data.get("fingerprint") is None


@pytest.mark.asyncio
async def test_list_accounts_shows_balance(client):
    acc_id = await _create_account_direct(opening_balance="1000.00")
    await _create_tx_for_account(acc_id, "200.00", "debit")
    await _create_tx_for_account(acc_id, "500.00", "credit")

    resp = await client.get("/accounts")
    assert resp.status_code == 200
    accounts = resp.json()
    assert len(accounts) == 1
    # balance = 1000 + (-200 + 500) = 1300
    assert accounts[0]["current_balance"] == "1300.00"


@pytest.mark.asyncio
async def test_update_account(client):
    acc_id = await _create_account_direct(name="Old Name")
    resp = await client.patch(f"/accounts/{acc_id}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_account_soft(client):
    acc_id = await _create_account_direct()
    resp = await client.delete(f"/accounts/{acc_id}")
    assert resp.status_code == 204

    list_resp = await client.get("/accounts")
    assert all(a["id"] != acc_id for a in list_resp.json())


@pytest.mark.asyncio
async def test_transfer_detect_no_pairs(client):
    resp = await client.post("/accounts/transfer-detect")
    assert resp.status_code == 200
    assert resp.json()["pairs_flagged"] == 0


@pytest.mark.asyncio
async def test_transfer_detect_creates_flag(client):
    """Two accounts with same-amount opposite-direction txns within 3 days → 1 pair."""
    acc1 = await _create_account_direct(name="Account A", type="checking")
    acc2 = await _create_account_direct(name="Account B", type="savings")
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        await conn.execute(
            """INSERT INTO transactions
               (date, amount, description, direction, account_id, status)
               VALUES ('2026-06-15', '500.00', 'Transfer out', 'debit', $1, 'active'),
                      ('2026-06-15', '500.00', 'Transfer in',  'credit', $2, 'active')""",
            acc1, acc2,
        )
    finally:
        await conn.close()

    resp = await client.post("/accounts/transfer-detect")
    assert resp.status_code == 200
    assert resp.json()["pairs_flagged"] == 1

    # Idempotent: re-running must not create new pairs (already tagged)
    resp2 = await client.post("/accounts/transfer-detect")
    assert resp2.json()["pairs_flagged"] == 0


@pytest.mark.asyncio
async def test_detect_account_returns_none_without_number(db_session):
    """detect_account on text with no numeric pattern returns None (non-fatal)."""
    from src.domain.services.statement_pipeline import detect_account
    result = await detect_account("No numbers here at all.", db_session)
    assert result is None


@pytest.mark.asyncio
async def test_detect_duplicates_flags_matching_txn(db_session):
    """_detect_duplicates creates a suspected_duplicate flag for same amount/direction/date."""
    from decimal import Decimal
    from datetime import datetime
    from sqlalchemy import select, text
    from src.domain.models.transaction import Transaction
    from src.domain.models.transaction_flag import TransactionFlag
    from src.domain.services.statement_pipeline import _detect_duplicates

    # Create account
    acc_id_row = await db_session.execute(
        text(
            "INSERT INTO accounts (name, type, currency, opening_balance) "
            "VALUES ('Test', 'checking', 'PHP', 0) RETURNING id"
        )
    )
    acc_id = acc_id_row.scalar()

    # Insert existing active transaction
    existing = Transaction(
        date=datetime(2026, 6, 15),
        description="Existing",
        amount=Decimal("100.00"),
        direction="debit",
        account_id=acc_id,
        status="active",
    )
    db_session.add(existing)
    await db_session.flush()

    # New transaction same amount/direction/date
    new_tx = Transaction(
        date=datetime(2026, 6, 15),
        description="Duplicate",
        amount=Decimal("100.00"),
        direction="debit",
        account_id=acc_id,
        status="staged",
    )
    db_session.add(new_tx)
    await db_session.flush()

    await _detect_duplicates([new_tx], acc_id, db_session)

    flags = (await db_session.execute(
        select(TransactionFlag).where(
            TransactionFlag.transaction_id == new_tx.id,
            TransactionFlag.flag_type == 'suspected_duplicate',
        )
    )).scalars().all()
    assert len(flags) == 1
    assert flags[0].flag_metadata["peer_id"] == existing.id

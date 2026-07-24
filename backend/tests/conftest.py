import asyncio
import os
import subprocess
import pytest
import pytest_asyncio
import asyncpg
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Must be set before src.main is imported (Settings() runs at import time)
os.environ.setdefault("APP_SECRET", "test-secret-key-that-is-at-least-32-chars!")

from src.main import app
from src.db.session import get_db

import os

# Allow overriding host/credentials for CI
_DB_HOST = os.environ.get("TEST_DB_HOST", "db")
_DB_USER = os.environ.get("DB_USER", "user")
_DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
TEST_DB_URL = f"postgresql+asyncpg://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:5432/spending_tracker_test"
TEST_DB_RAW = f"postgresql://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:5432/spending_tracker_test"
TEST_DB_ASYNCPG = f"postgresql+asyncpg://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:5432/spending_tracker_test"

# Engine created lazily in setup_db to bind to the correct event loop
_engine_test = None
_TestingSessionLocal = None


async def _create_test_db():
    """Create spending_tracker_test DB if it doesn't exist."""
    conn = await asyncpg.connect(f"postgresql://user:password@{_DB_HOST}:5432/postgres")
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'spending_tracker_test'"
        )
        if not exists:
            await conn.execute("CREATE DATABASE spending_tracker_test")
    finally:
        await conn.close()


def _run_migrations():
    """Run alembic upgrade head via subprocess to avoid asyncio.run() nested-loop conflict."""
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        env={
            **__import__("os").environ,
            "DATABASE_URL": TEST_DB_ASYNCPG,
        },
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade head failed:\n{result.stdout}\n{result.stderr}")


def _drop_migrations():
    """Run alembic downgrade base via subprocess."""
    result = subprocess.run(
        ["alembic", "downgrade", "base"],
        env={
            **__import__("os").environ,
            "DATABASE_URL": TEST_DB_ASYNCPG,
        },
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"alembic downgrade base failed:\n{result.stdout}\n{result.stderr}")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    global _engine_test, _TestingSessionLocal
    await _create_test_db()
    _run_migrations()
    # Create engine bound to the current (session) event loop
    _engine_test = create_async_engine(TEST_DB_URL, pool_size=5, pool_pre_ping=True)
    _TestingSessionLocal = sessionmaker(_engine_test, class_=AsyncSession, expire_on_commit=False)
    yield
    await _engine_test.dispose()
    _drop_migrations()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    """Truncate all data tables between tests using a fresh asyncpg connection."""
    yield
    # Use a fresh asyncpg connection to avoid SQLAlchemy pool / event-loop issues
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        await conn.execute(
            "TRUNCATE accounts, investment_transactions, transactions, statements, categories RESTART IDENTITY CASCADE"
        )
        await conn.execute(
            "UPDATE app_settings SET ocr_provider='tesseract', anthropic_api_key=NULL, openai_api_key=NULL WHERE id=1"
        )
    finally:
        await conn.close()


async def override_get_db():
    async with _TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    async with _TestingSessionLocal() as session:
        yield session

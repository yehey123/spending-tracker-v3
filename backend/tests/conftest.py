import asyncio
import os
import subprocess
import uuid
import pytest
import pytest_asyncio
import asyncpg
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Must be set before src.main is imported (Settings() runs at import time)
os.environ.setdefault("APP_SECRET", "test-secret-key-that-is-at-least-32-chars!")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-that-is-at-least-32-chars!")

from src.main import app
from src.core import cache
from src.core.auth import create_access_token, hash_password
from src.core.deps import get_current_user
from src.db.session import get_db
from src.domain.models.user import User

import os

# Allow overriding host/credentials for CI
_DB_HOST = os.environ.get("TEST_DB_HOST", "db")
_DB_USER = os.environ.get("DB_USER", "user")
_DB_PASSWORD = os.environ.get("DB_PASSWORD", "password")
TEST_DB_URL = f"postgresql+asyncpg://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:5432/spending_tracker_test"
TEST_DB_RAW = f"postgresql://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:5432/spending_tracker_test"
TEST_DB_ASYNCPG = f"postgresql+asyncpg://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:5432/spending_tracker_test"

_TEST_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_TEST_USER_EMAIL = "testuser@test.com"

# Engine created lazily in setup_db to bind to the correct event loop
_engine_test = None
_TestingSessionLocal = None
_test_user: User | None = None
_test_user_token: str | None = None


async def _create_test_db():
    """Create spending_tracker_test DB if it doesn't exist."""
    conn = await asyncpg.connect(f"postgresql://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:5432/postgres")
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


@pytest.fixture(autouse=True)
def clear_cache():
    """Flush the analytics cache before each test for isolation."""
    cache.clear()
    yield
    cache.clear()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    global _engine_test, _TestingSessionLocal, _test_user, _test_user_token
    await _create_test_db()
    _run_migrations()
    # Create engine bound to the current (session) event loop
    _engine_test = create_async_engine(TEST_DB_URL, pool_size=5, pool_pre_ping=True)
    _TestingSessionLocal = sessionmaker(_engine_test, class_=AsyncSession, expire_on_commit=False)

    # Create a persistent test user that all tests share (users table has no RLS)
    async with _TestingSessionLocal() as db:
        # Bypass RLS for setup — is_admin grants full access to RLS-protected tables
        await db.execute(text("SELECT set_config('app.is_admin', 'true', false)"))
        result = await db.execute(select(User).where(User.email == _TEST_USER_EMAIL))
        existing = result.scalar_one_or_none()
        if existing is None:
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            # Insert with a fixed UUID so tests are deterministic
            await db.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, is_admin) "
                    "VALUES (:id, :email, :pw, true) ON CONFLICT DO NOTHING"
                ),
                {"id": str(_TEST_USER_ID), "email": _TEST_USER_EMAIL,
                 "pw": hash_password("testpassword")},
            )
            await db.commit()
            result2 = await db.execute(select(User).where(User.email == _TEST_USER_EMAIL))
            _test_user = result2.scalar_one()
        else:
            _test_user = existing
        _test_user_token = create_access_token(_test_user.id, is_admin=True)

    yield
    await _engine_test.dispose()
    _drop_migrations()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    """Truncate all data tables between tests using a fresh asyncpg connection."""
    yield
    conn = await asyncpg.connect(TEST_DB_RAW)
    try:
        # TRUNCATE bypasses RLS; used for fast bulk cleanup
        await conn.execute(
            "TRUNCATE accounts, investment_transactions, transactions, statements, "
            "categories, app_settings, refresh_tokens, oauth_accounts "
            "RESTART IDENTITY CASCADE"
        )
        # Remove any extra users created by individual auth tests; keep the shared test user
        await conn.execute(
            f"DELETE FROM users WHERE email != '{_TEST_USER_EMAIL}'"
        )
    finally:
        await conn.close()


async def override_get_db():
    """Test DB session with admin bypass so RLS does not interfere with test data setup."""
    async with _TestingSessionLocal() as session:
        await session.execute(text("SELECT set_config('app.is_admin', 'true', false)"))
        if _test_user is not None:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, false)"),
                {"uid": str(_test_user.id)},
            )
        yield session


async def override_get_current_user() -> User:
    """Return the shared test user — no JWT required in test requests."""
    return _test_user


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Direct DB session with admin RLS bypass and test user context."""
    async with _TestingSessionLocal() as session:
        await session.execute(text("SELECT set_config('app.is_admin', 'true', false)"))
        if _test_user is not None:
            await session.execute(
                text("SELECT set_config('app.user_id', :uid, false)"),
                {"uid": str(_test_user.id)},
            )
        yield session


@pytest_asyncio.fixture
def test_user() -> User:
    """The shared test user for this session."""
    return _test_user


@pytest_asyncio.fixture
def test_user_token() -> str:
    """JWT access token for the shared test user."""
    return _test_user_token

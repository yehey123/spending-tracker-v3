import asyncio
import pytest
import pytest_asyncio
import asyncpg
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

from src.main import app
from src.db.session import get_db

TEST_DB_URL = "postgresql+asyncpg://user:password@db:5432/spending_tracker_test"
TEST_DB_RAW = "postgresql://user:password@db:5432/spending_tracker_test"

engine_test = create_async_engine(TEST_DB_URL, pool_size=5)
TestingSessionLocal = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)


async def _create_test_db():
    """Create spending_tracker_test DB if it doesn't exist."""
    conn = await asyncpg.connect("postgresql://user:password@db:5432/spending_tracker")
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'spending_tracker_test'"
        )
        if not exists:
            await conn.execute("CREATE DATABASE spending_tracker_test")
    finally:
        await conn.close()


def _run_migrations():
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_RAW)
    command.upgrade(cfg, "head")


def _drop_migrations():
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_DB_RAW)
    command.downgrade(cfg, "base")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    await _create_test_db()
    _run_migrations()
    yield
    _drop_migrations()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    """Truncate all data tables between tests."""
    yield
    async with engine_test.begin() as conn:
        await conn.execute(
            __import__("sqlalchemy").text(
                "TRUNCATE transactions, statements, categories RESTART IDENTITY CASCADE"
            )
        )
        # Reset app_settings seed
        await conn.execute(
            __import__("sqlalchemy").text(
                "UPDATE app_settings SET ocr_provider='tesseract', anthropic_api_key=NULL, openai_api_key=NULL WHERE id=1"
            )
        )


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

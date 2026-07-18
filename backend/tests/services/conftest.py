"""Conftest for services tests — no Postgres required.

The parent conftest (tests/conftest.py) imports asyncpg and tries to connect to Postgres
for its session-scope fixtures.  Services tests are pure unit tests that only need SQLite,
so we override those fixtures here to make the suite runnable without a live DB.
"""

import pytest
import pytest_asyncio


# Override the session-scope Postgres fixtures from the parent conftest so they are no-ops.


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():  # type: ignore[override]
    """No-op override — services tests do not require Postgres."""
    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():  # type: ignore[override]
    """No-op override — services tests do not require table truncation."""
    yield

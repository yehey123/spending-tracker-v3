import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.db.session import _bind_rls_context
from tests.conftest import TEST_DB_URL

_GUC = text("SELECT current_setting('app.user_id', true)")


async def test_rls_context_reapplied_after_commit():
    uid = uuid.uuid4()
    engine = create_async_engine(TEST_DB_URL)
    try:
        async with sessionmaker(engine, class_=AsyncSession)() as session:
            _bind_rls_context(session, uid, False)
            assert (await session.execute(_GUC)).scalar() == str(uid)
            await session.commit()
            assert (await session.execute(_GUC)).scalar() == str(uid)
    finally:
        await engine.dispose()


async def test_rls_context_does_not_leak_to_pool():
    uid = uuid.uuid4()
    engine = create_async_engine(TEST_DB_URL, pool_size=1, max_overflow=0)
    try:
        async with sessionmaker(engine, class_=AsyncSession)() as session:
            _bind_rls_context(session, uid, True)
            await session.execute(text("SELECT 1"))
            await session.commit()  # connection returns to the pool; session stays open
            async with engine.connect() as conn:
                value = (await conn.execute(_GUC)).scalar()
                admin = (await conn.execute(text("SELECT current_setting('app.is_admin', true)"))).scalar()
            assert value in (None, "")
            assert admin in (None, "", "false")
    finally:
        await engine.dispose()

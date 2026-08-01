from contextlib import asynccontextmanager

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings

_runtime_url = settings.app_db_url or settings.database_url
engine = create_async_engine(_runtime_url, pool_size=10, max_overflow=20)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db(request: Request):
    """Request-scoped DB session. Sets app.user_id / app.is_admin for RLS, then resets."""
    async with AsyncSessionLocal() as session:
        user_id = getattr(request.state, 'user_id', None)
        is_admin = getattr(request.state, 'is_admin', False)
        try:
            if user_id is not None:
                # Use set_config() — SET command does not accept bind parameters.
                await session.execute(
                    text("SELECT set_config('app.user_id', :uid, false)"),
                    {"uid": str(user_id)},
                )
                await session.execute(
                    text("SELECT set_config('app.is_admin', :adm, false)"),
                    {"adm": 'true' if is_admin else 'false'},
                )
            yield session
        finally:
            if user_id is not None:
                try:
                    await session.execute(text("RESET app.user_id"))
                    await session.execute(text("RESET app.is_admin"))
                except Exception:
                    pass  # session may be in a rolled-back state; pool will reset


@asynccontextmanager
async def get_admin_db():
    """System-task session with admin bypass — for scheduled jobs and lifespan tasks."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            text("SELECT set_config('app.is_admin', 'true', false)")
        )
        try:
            yield session
        finally:
            try:
                await session.execute(text("RESET app.is_admin"))
            except Exception:
                pass

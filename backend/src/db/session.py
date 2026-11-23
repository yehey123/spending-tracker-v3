from contextlib import asynccontextmanager

from fastapi import Request
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings

_runtime_url = settings.app_db_url or settings.database_url
engine = create_async_engine(_runtime_url, pool_size=10, max_overflow=20)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _bind_rls_context(session: AsyncSession, user_id, is_admin: bool) -> None:
    """Apply app.user_id / app.is_admin to every transaction the session begins.

    The settings are transaction-local (set_config(..., true)) and re-applied on
    each transaction start. This is deliberate: an AsyncSession returns its
    connection to the pool at every commit(), so the next statement in the same
    request can run on a DIFFERENT pooled connection. Session-level settings
    would be missing there (RLS hides the request's own rows) or, worse, a
    connection could still carry another request's tenant or admin bypass.
    Transaction-local settings vanish at commit/rollback, so nothing leaks to
    the pool.

    Policies read app.user_id as NULLIF(current_setting(..., TRUE), '')::uuid,
    so an empty string means "no user" and is safe.
    """
    uid = "" if user_id is None else str(user_id)
    adm = "true" if is_admin else "false"

    @event.listens_for(session.sync_session, "after_begin")
    def _set_rls(_sess, _txn, connection):
        connection.execute(
            text(
                "SELECT set_config('app.user_id', :uid, true), "
                "set_config('app.is_admin', :adm, true)"
            ),
            {"uid": uid, "adm": adm},
        )


async def get_db(request: Request):
    """Request-scoped DB session. app.user_id / app.is_admin are set per transaction for RLS."""
    async with AsyncSessionLocal() as session:
        user_id = getattr(request.state, 'user_id', None)
        is_admin = getattr(request.state, 'is_admin', False)
        if user_id is not None:
            _bind_rls_context(session, user_id, is_admin)
        yield session


@asynccontextmanager
async def get_admin_db():
    """System-task session with admin bypass — for scheduled jobs and lifespan tasks."""
    async with AsyncSessionLocal() as session:
        _bind_rls_context(session, None, True)
        yield session

import asyncio
import logging
import os
from contextlib import asynccontextmanager

os.umask(0o077)  # PIL scratch files are readable only by owner

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.config import settings as app_settings
from src.core.deps import get_current_user
from src.core.middleware import UserContextMiddleware
from src.db.session import engine
from src.domain.services.category_seeder import seed_default_categories
from src.domain.services.exchange_rate import exchange_rate_service
import src.domain.models  # noqa: F401 — registers all ORM models with SQLAlchemy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.tasks.ttl_cleanup import run_ttl_cleanup
from src.tasks.monthly_rollover import run_monthly_rollover
from src.domain.services.model_sync import sync_all as sync_models

_scheduler = AsyncIOScheduler()
_scheduler.add_job(run_ttl_cleanup, 'cron', hour=2)
_scheduler.add_job(
    lambda: asyncio.ensure_future(sync_models()),
    'cron', hour=3, minute=0,
)
_scheduler.add_job(
    lambda: asyncio.ensure_future(run_monthly_rollover()),
    'cron',
    day=1,
    hour=0,
    minute=5,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.db.session import get_admin_db
    from src.core.bootstrap import run_admin_bootstrap
    async with get_admin_db() as db:
        await seed_default_categories(db)
        await run_admin_bootstrap(db)
    _scheduler.start()
    await exchange_rate_service.init_db()
    asyncio.create_task(sync_models())
    yield
    _scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title="Spending Tracker", version="0.1.0", lifespan=lifespan, redirect_slashes=False)

_default_cors_origins = [
    "http://localhost",
    "http://localhost:3000",
    "capacitor://localhost",
    "http://localhost:8100",
]
_configured_cors_origins = [
    origin.strip() for origin in app_settings.cors_origins.split(",") if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_cors_origins or _default_cors_origins,
    allow_methods=["*"],
    allow_headers=["X-API-Token", "Content-Type", "Authorization"],
)
app.add_middleware(UserContextMiddleware)

from src.api.routes import (  # noqa: E402
    accounts,
    admin as admin_router,
    analytics,
    auth as auth_router,
    categories,
    credits,
    exchange_rates,
    flags,
    health,
    invite,
    investment_transactions,
    portfolio,
    receipts,
    settings,
    staged_transactions,
    statements,
    transactions,
)

app.include_router(health.router)
# E11: invite gate — public endpoints (no require_token)
app.include_router(invite.router, tags=["invite-gate"])
# E12: auth — login/register/OAuth must be public; router prefix=/auth
app.include_router(auth_router.router)
app.include_router(
    accounts.router, prefix="/accounts", tags=["accounts"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    categories.router, prefix="/categories", tags=["categories"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    statements.router, prefix="/statements", tags=["statements"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    transactions.router, prefix="/transactions", tags=["transactions"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    staged_transactions.router,
    prefix="/staged-transactions",
    tags=["staged-transactions"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    analytics.router, prefix="/analytics", tags=["analytics"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    settings.router, prefix="/settings", tags=["settings"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    exchange_rates.router,
    prefix="/exchange-rates",
    tags=["exchange-rates"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    receipts.router, prefix="/receipts", tags=["receipts"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    flags.router, prefix="/flags", tags=["flags"], dependencies=[Depends(get_current_user)]
)
app.include_router(
    investment_transactions.router,
    prefix="/accounts/{account_id}/investment-transactions",
    tags=["investment-transactions"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    portfolio.router,
    prefix="/accounts/{account_id}/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(get_current_user)],
)
app.include_router(
    credits.router,
    prefix="/credits",
    tags=["credits"],
    dependencies=[Depends(get_current_user)],
)
# E17: admin — /admin/bootstrap is public; all other /admin/* require require_admin dep on each handler
app.include_router(admin_router.router)

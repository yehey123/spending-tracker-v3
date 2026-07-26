import asyncio
import logging
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
)

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.core.auth import require_token
from src.core.config import settings as app_settings
from src.db.session import AsyncSessionLocal, engine
from src.domain.services.category_seeder import seed_default_categories
from src.domain.services.exchange_rate import exchange_rate_service
import src.domain.models  # noqa: F401 — registers all ORM models with SQLAlchemy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.tasks.ttl_cleanup import run_ttl_cleanup
from src.domain.services.model_sync import sync_all as sync_models

_scheduler = AsyncIOScheduler()
_scheduler.add_job(run_ttl_cleanup, 'cron', hour=2)
_scheduler.add_job(
    lambda: asyncio.ensure_future(sync_models()),
    'cron', hour=3, minute=0,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as db:
        await seed_default_categories(db)
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

from src.api.routes import (  # noqa: E402
    accounts,
    analytics,
    categories,
    exchange_rates,
    flags,
    health,
    investment_transactions,
    portfolio,
    receipts,
    settings,
    staged_transactions,
    statements,
    transactions,
)

app.include_router(health.router)
app.include_router(
    accounts.router, prefix="/accounts", tags=["accounts"], dependencies=[Depends(require_token)]
)
app.include_router(
    categories.router, prefix="/categories", tags=["categories"], dependencies=[Depends(require_token)]
)
app.include_router(
    statements.router, prefix="/statements", tags=["statements"], dependencies=[Depends(require_token)]
)
app.include_router(
    transactions.router, prefix="/transactions", tags=["transactions"], dependencies=[Depends(require_token)]
)
app.include_router(
    staged_transactions.router,
    prefix="/staged-transactions",
    tags=["staged-transactions"],
    dependencies=[Depends(require_token)],
)
app.include_router(
    analytics.router, prefix="/analytics", tags=["analytics"], dependencies=[Depends(require_token)]
)
app.include_router(
    settings.router, prefix="/settings", tags=["settings"], dependencies=[Depends(require_token)]
)
app.include_router(
    exchange_rates.router,
    prefix="/exchange-rates",
    tags=["exchange-rates"],
    dependencies=[Depends(require_token)],
)
app.include_router(
    receipts.router, prefix="/receipts", tags=["receipts"], dependencies=[Depends(require_token)]
)
app.include_router(
    flags.router, prefix="/flags", tags=["flags"], dependencies=[Depends(require_token)]
)
app.include_router(
    investment_transactions.router,
    prefix="/accounts/{account_id}/investment-transactions",
    tags=["investment-transactions"],
    dependencies=[Depends(require_token)],
)
app.include_router(
    portfolio.router,
    prefix="/accounts/{account_id}/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(require_token)],
)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.session import AsyncSessionLocal, engine
from src.domain.services.category_seeder import seed_default_categories
from src.domain.services.exchange_rate import exchange_rate_service
import src.domain.models  # noqa: F401 — registers all ORM models with SQLAlchemy
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.tasks.ttl_cleanup import run_ttl_cleanup

_scheduler = AsyncIOScheduler()
_scheduler.add_job(run_ttl_cleanup, 'cron', hour=2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as db:
        await seed_default_categories(db)
    _scheduler.start()
    await exchange_rate_service.init_db()
    yield
    _scheduler.shutdown(wait=False)
    await engine.dispose()


app = FastAPI(title="Spending Tracker", version="0.1.0", lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
app.include_router(categories.router, prefix="/categories", tags=["categories"])
app.include_router(statements.router, prefix="/statements", tags=["statements"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(staged_transactions.router, prefix="/staged-transactions", tags=["staged-transactions"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(exchange_rates.router, prefix="/exchange-rates", tags=["exchange-rates"])
app.include_router(receipts.router, prefix="/receipts", tags=["receipts"])
app.include_router(flags.router, prefix="/flags", tags=["flags"])
app.include_router(
    investment_transactions.router,
    prefix="/accounts/{account_id}/investment-transactions",
    tags=["investment-transactions"],
)
app.include_router(
    portfolio.router,
    prefix="/accounts/{account_id}/portfolio",
    tags=["portfolio"],
)

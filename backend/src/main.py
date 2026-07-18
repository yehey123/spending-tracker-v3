from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.session import AsyncSessionLocal, engine
from src.domain.services.category_seeder import seed_default_categories
from src.domain.services.exchange_rate import exchange_rate_service
import src.domain.models  # noqa: F401 — registers all ORM models with SQLAlchemy


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as db:
        await seed_default_categories(db)
    await exchange_rate_service.init_db()
    yield
    await engine.dispose()


app = FastAPI(title="Spending Tracker", version="0.1.0", lifespan=lifespan, redirect_slashes=False)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.api.routes import (  # noqa: E402
    analytics,
    categories,
    exchange_rates,
    health,
    settings,
    statements,
    transactions,
)

app.include_router(health.router)
app.include_router(categories.router, prefix="/categories", tags=["categories"])
app.include_router(statements.router, prefix="/statements", tags=["statements"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(exchange_rates.router, prefix="/exchange-rates", tags=["exchange-rates"])

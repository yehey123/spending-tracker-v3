"""Health check route."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db

router = APIRouter()

# Every table created by migrations must appear here.
# A missing entry → 503, which means migrations haven't run.
_REQUIRED_TABLES = {"app_settings", "categories", "statements", "transactions"}


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ANY(:names)"
            ),
            {"names": list(_REQUIRED_TABLES)},
        )
        found = {row[0] for row in result}
        missing = _REQUIRED_TABLES - found
        if missing:
            raise HTTPException(
                status_code=503,
                detail=f"Migrations not applied — missing tables: {sorted(missing)}",
            )
        return {"status": "healthy", "tables": sorted(found)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unhealthy: {e}")

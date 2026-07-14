"""Settings routes: read and update OCR provider configuration."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.settings import SettingsOut, SettingsPut
from src.db.session import get_db
from src.domain.models.app_settings import AppSettings

router = APIRouter()


async def _get_settings(db: AsyncSession) -> AppSettings:
    """Fetch the single app_settings row (id=1)."""
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        # Seed the row if it somehow doesn't exist (migration should have created it)
        row = AppSettings(id=1, ocr_provider="tesseract")
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


def _to_out(row: AppSettings) -> SettingsOut:
    return SettingsOut(
        ocr_provider=row.ocr_provider,
        anthropic_api_key_set=bool(row.anthropic_api_key),
        openai_api_key_set=bool(row.openai_api_key),
    )


@router.get("", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return current OCR settings. API key values are never returned."""
    row = await _get_settings(db)
    return _to_out(row)


@router.put("", response_model=SettingsOut)
async def update_settings(body: SettingsPut, db: AsyncSession = Depends(get_db)):
    """Update OCR provider and/or API keys.

    Rules:
    - Omit a key field to leave it unchanged.
    - Send ``null`` for a key to clear it.
    - Switching to claude/openai requires the corresponding key in the request
      or already stored in the DB.
    """
    row = await _get_settings(db)

    # Determine effective key values after the update (before writing)
    # body.anthropic_api_key == None → clear; field absent → leave unchanged
    # Since Pydantic gives us None for both "omitted" and "null" in SettingsPut,
    # we use model_fields_set to distinguish.
    fields_set = body.model_fields_set

    new_anthropic = (
        body.anthropic_api_key if "anthropic_api_key" in fields_set else row.anthropic_api_key
    )
    new_openai = (
        body.openai_api_key if "openai_api_key" in fields_set else row.openai_api_key
    )

    # Validate that the required key will be present after the update
    if body.ocr_provider == "claude" and not new_anthropic:
        raise HTTPException(
            status_code=422,
            detail="Provider 'claude' requires anthropic_api_key to be set.",
        )
    if body.ocr_provider == "openai" and not new_openai:
        raise HTTPException(
            status_code=422,
            detail="Provider 'openai' requires openai_api_key to be set.",
        )

    # Apply updates
    row.ocr_provider = body.ocr_provider
    if "anthropic_api_key" in fields_set:
        row.anthropic_api_key = body.anthropic_api_key
    if "openai_api_key" in fields_set:
        row.openai_api_key = body.openai_api_key

    await db.commit()
    await db.refresh(row)
    return _to_out(row)

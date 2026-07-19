"""Settings routes: read and update OCR provider and currency configuration."""

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
        home_currency=row.home_currency,
        review_before_commit=row.review_before_commit,
        ai_category_confidence_auto=row.ai_category_confidence_auto,
        ai_category_confidence_suggest=row.ai_category_confidence_suggest,
        ai_provider=row.ai_provider,
        ai_model=row.ai_model,
        ai_api_url=row.ai_api_url,
        gemini_api_key_set=bool(row.gemini_api_key),
        google_project_id=row.google_project_id,
        google_location=row.google_location,
    )


@router.get("", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return current settings. API key values are never returned."""
    row = await _get_settings(db)
    return _to_out(row)


@router.put("", response_model=SettingsOut)
async def update_settings(body: SettingsPut, db: AsyncSession = Depends(get_db)):
    """Update settings. Only provided fields are changed (use model_fields_set)."""
    row = await _get_settings(db)

    fields_set = body.model_fields_set

    new_anthropic = (
        body.anthropic_api_key if "anthropic_api_key" in fields_set else row.anthropic_api_key
    )
    new_openai = body.openai_api_key if "openai_api_key" in fields_set else row.openai_api_key

    if "ocr_provider" in fields_set:
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
        row.ocr_provider = body.ocr_provider

    if "anthropic_api_key" in fields_set:
        row.anthropic_api_key = body.anthropic_api_key
    if "openai_api_key" in fields_set:
        row.openai_api_key = body.openai_api_key
    if "home_currency" in fields_set:
        row.home_currency = body.home_currency
    if "review_before_commit" in fields_set and body.review_before_commit is not None:
        row.review_before_commit = body.review_before_commit
    if "ai_category_confidence_auto" in fields_set and body.ai_category_confidence_auto is not None:
        row.ai_category_confidence_auto = body.ai_category_confidence_auto
    if (
        "ai_category_confidence_suggest" in fields_set
        and body.ai_category_confidence_suggest is not None
    ):
        row.ai_category_confidence_suggest = body.ai_category_confidence_suggest
    if "ai_provider" in fields_set and body.ai_provider is not None:
        row.ai_provider = body.ai_provider
    if "ai_model" in fields_set:
        row.ai_model = body.ai_model
    if "ai_api_url" in fields_set:
        row.ai_api_url = body.ai_api_url
    if "gemini_api_key" in fields_set:
        row.gemini_api_key = body.gemini_api_key
    if "google_project_id" in fields_set:
        row.google_project_id = body.google_project_id
    if "google_location" in fields_set:
        row.google_location = body.google_location

    await db.commit()
    await db.refresh(row)
    return _to_out(row)

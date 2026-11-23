"""Settings routes: read and update OCR provider and currency configuration."""

import uuid
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.settings import ConfigFieldOut, ProviderOut, SettingsOut, SettingsPut
from src.core.config import settings as app_config
from src.core.crypto import encrypt_secret
from src.core.deps import get_current_user
from src.db.session import get_db
from src.domain.models.app_settings import AppSettings
from src.domain.models.user import User
from src.plugins import registry

router = APIRouter()


async def _get_settings(db: AsyncSession, user_id: uuid.UUID) -> AppSettings:
    """Fetch the app_settings row for this user, creating it if absent."""
    result = await db.execute(select(AppSettings).where(AppSettings.user_id == user_id))
    row = result.scalar_one_or_none()
    if row is None:
        from src.core.config import settings as _cfg

        row = AppSettings(
            user_id=user_id,
            ocr_provider=_cfg.ocr_provider,
            anthropic_api_key=encrypt_secret(_cfg.anthropic_api_key),
            openai_api_key=encrypt_secret(_cfg.openai_api_key),
            gemini_api_key=encrypt_secret(_cfg.gemini_api_key),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


def _field_attr(f, name, default=None):
    if isinstance(f, dict):
        return f.get(name, default)
    return getattr(f, name, default)


def _providers_out(row: AppSettings) -> list[ProviderOut]:
    out = []
    for key, desc in registry.available().items():
        fields = []
        for f in getattr(desc, "config_fields", ()) or ():
            name = _field_attr(f, "name")
            if not name:
                continue
            fields.append(
                ConfigFieldOut(
                    name=name,
                    label=_field_attr(f, "label", name),
                    secret=bool(_field_attr(f, "secret", False)),
                    required=bool(_field_attr(f, "required", False)),
                    set=bool(getattr(row, name, None)),
                )
            )
        out.append(ProviderOut(key=key, label=desc.label, config_fields=fields))
    return out


def _to_out(row: AppSettings) -> SettingsOut:
    return SettingsOut(
        ocr_provider=row.ocr_provider,
        available_providers=_providers_out(row),
        provider_installed=registry.find_ocr(row.ocr_provider) is not None,
        anthropic_api_key_set=bool(row.anthropic_api_key),
        openai_api_key_set=bool(row.openai_api_key),
        home_currency=row.home_currency,
        review_before_commit=row.review_before_commit,
        ai_category_confidence_auto=row.ai_category_confidence_auto,
        ai_category_confidence_suggest=row.ai_category_confidence_suggest,
        ai_model=row.ai_model,
        gemini_api_key_set=bool(row.gemini_api_key),
        google_project_id=row.google_project_id,
        google_location=row.google_location,
        max_output_tokens=row.max_output_tokens,
        dev_mode=row.dev_mode,
        dev_mode_available=app_config.app_env != "production",
    )


@router.get("", response_model=SettingsOut)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return current settings. API key values are never returned."""
    row = await _get_settings(db, current_user.id)
    return _to_out(row)


@router.put("", response_model=SettingsOut)
async def update_settings(
    body: SettingsPut,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update settings. Only provided fields are changed (use model_fields_set)."""
    row = await _get_settings(db, current_user.id)

    fields_set = body.model_fields_set

    if "ocr_provider" in fields_set:
        desc = registry.find_ocr(body.ocr_provider) if body.ocr_provider else None
        if desc is None:
            raise HTTPException(
                status_code=422,
                detail=f"Provider '{body.ocr_provider}' is not installed.",
            )
        if getattr(desc, "config_fields", None):
            would_be = SimpleNamespace(
                **{c.name: getattr(row, c.name) for c in AppSettings.__table__.columns}
            )
            for name in fields_set:
                if hasattr(would_be, name) and name != "ocr_provider":
                    setattr(would_be, name, getattr(body, name))
            if not desc.has_credentials(would_be):
                raise HTTPException(
                    status_code=422,
                    detail=f"Provider '{body.ocr_provider}' requires credentials to be set.",
                )
        row.ocr_provider = body.ocr_provider

    if "anthropic_api_key" in fields_set:
        row.anthropic_api_key = encrypt_secret(body.anthropic_api_key)
    if "openai_api_key" in fields_set:
        row.openai_api_key = encrypt_secret(body.openai_api_key)
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
    if "ai_model" in fields_set:
        row.ai_model = body.ai_model
    if "gemini_api_key" in fields_set:
        row.gemini_api_key = encrypt_secret(body.gemini_api_key)
    if "google_project_id" in fields_set:
        row.google_project_id = body.google_project_id
    if "google_location" in fields_set:
        row.google_location = body.google_location

    if "max_output_tokens" in fields_set:
        if body.max_output_tokens is not None:
            from src.domain.models.model_cache import ModelCache

            model_name = body.ai_model or row.ai_model
            if model_name:
                known = (
                    await db.execute(
                        select(ModelCache.max_output_tokens)
                        .where(ModelCache.model_id == model_name)
                        .where(ModelCache.max_output_tokens.is_not(None))
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if known is not None and body.max_output_tokens > known:
                    raise HTTPException(
                        status_code=422,
                        detail=f"'{model_name}' supports at most {known:,} output tokens.",
                    )
        row.max_output_tokens = body.max_output_tokens

    if "dev_mode" in fields_set and body.dev_mode is not None:
        if body.dev_mode and app_config.app_env == "production":
            raise HTTPException(status_code=403, detail="dev_mode is not available in production.")
        row.dev_mode = body.dev_mode

    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.get("/models")
async def list_models(
    provider: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import datetime, timedelta, timezone

    from src.domain.models.model_cache import ModelCache

    q = select(ModelCache)
    if provider:
        q = q.where(ModelCache.provider == provider)
    q = q.order_by(ModelCache.provider, ModelCache.model_id)
    rows = (await db.execute(q)).scalars().all()

    if rows:
        oldest = min(r.refreshed_at for r in rows)
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - oldest > timedelta(days=7):
            import asyncio

            asyncio.create_task(registry.sync_all_models())

    return {
        "provider": provider,
        "models": [
            {
                "model_id": r.model_id,
                "display_name": r.display_name,
                "max_output_tokens": r.max_output_tokens,
                "source": r.source,
                "provider": r.provider,
            }
            for r in rows
        ],
    }


@router.post("/models/refresh")
async def refresh_models(current_user: User = Depends(get_current_user)):
    counts = await registry.sync_all_models()
    return {"synced": counts}

"""Sync available AI models into model_cache from provider APIs (with seed fallback)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.db.session import AsyncSessionLocal
from src.domain.models.app_settings import AppSettings
from src.domain.models.model_cache import ModelCache
from src.domain.services.model_registry import SEED, get_limit

logger = logging.getLogger(__name__)


async def _upsert(db, rows: list[dict]) -> int:
    if not rows:
        return 0
    stmt = pg_insert(ModelCache).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["provider", "model_id"],
        set_={
            "display_name": stmt.excluded.display_name,
            "max_output_tokens": stmt.excluded.max_output_tokens,
            "source": stmt.excluded.source,
            "refreshed_at": stmt.excluded.refreshed_at,
        },
    )
    await db.execute(stmt)
    return len(rows)


async def _seed_provider(db, provider: str) -> int:
    if provider not in SEED:
        return 0
    now = datetime.now(timezone.utc)
    rows = [
        {
            "provider": provider,
            "model_id": model_id,
            "display_name": display_name,
            "max_output_tokens": tokens,
            "source": "seed",
            "refreshed_at": now,
        }
        for model_id, display_name, tokens in SEED[provider]
    ]
    # ON CONFLICT DO NOTHING for seed rows — never overwrite api-sourced data
    stmt = pg_insert(ModelCache).values(rows).on_conflict_do_nothing()
    await db.execute(stmt)
    return len(rows)


async def sync_gemini(db, settings: AppSettings) -> int:
    api_key = getattr(settings, "gemini_api_key", None)
    if not api_key:
        return await _seed_provider(db, "gemini")
    try:
        now = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()
        rows = []
        for m in data.get("models", []):
            model_id = m.get("name", "").removeprefix("models/")
            if not model_id:
                continue
            rows.append({
                "provider": "gemini",
                "model_id": model_id,
                "display_name": m.get("displayName"),
                "max_output_tokens": m.get("outputTokenLimit"),
                "source": "api",
                "refreshed_at": now,
            })
        return await _upsert(db, rows)
    except Exception as exc:
        logger.warning("sync_gemini failed (%s); seeding fallback", exc)
        return await _seed_provider(db, "gemini")


async def sync_vertex(db, settings: AppSettings) -> int:
    project = getattr(settings, "google_project_id", None)
    if not project:
        return await _seed_provider(db, "vertex")
    try:
        import google.auth
        import google.auth.transport.requests as _greq
        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(_greq.Request())
        now = datetime.now(timezone.utc)
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                headers={"Authorization": f"Bearer {creds.token}"},
            )
            resp.raise_for_status()
            data = resp.json()
        rows = []
        for m in data.get("models", []):
            model_id = m.get("name", "").removeprefix("models/")
            if not model_id:
                continue
            rows.append({
                "provider": "vertex",
                "model_id": model_id,
                "display_name": m.get("displayName"),
                "max_output_tokens": m.get("outputTokenLimit"),
                "source": "api",
                "refreshed_at": now,
            })
        return await _upsert(db, rows)
    except Exception as exc:
        logger.warning("sync_vertex failed (%s); seeding fallback", exc)
        return await _seed_provider(db, "vertex")


async def sync_openai(db, settings: AppSettings) -> int:
    api_key = getattr(settings, "openai_api_key", None)
    if not api_key:
        return await _seed_provider(db, "openai")
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        now = datetime.now(timezone.utc)
        prefixes = ("gpt-", "o1", "o3", "o4", "chatgpt-")
        rows = []
        async for m in await client.models.list():
            if not any(m.id.startswith(p) for p in prefixes):
                continue
            rows.append({
                "provider": "openai",
                "model_id": m.id,
                "display_name": m.id,
                "max_output_tokens": get_limit(m.id),
                "source": "api",
                "refreshed_at": now,
            })
        return await _upsert(db, rows)
    except Exception as exc:
        logger.warning("sync_openai failed (%s); seeding fallback", exc)
        return await _seed_provider(db, "openai")


async def sync_claude(db, settings: AppSettings) -> int:
    api_key = getattr(settings, "anthropic_api_key", None)
    if not api_key:
        return await _seed_provider(db, "claude")
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        now = datetime.now(timezone.utc)
        models = client.models.list()
        rows = [
            {
                "provider": "claude",
                "model_id": m.id,
                "display_name": getattr(m, "display_name", m.id),
                "max_output_tokens": get_limit(m.id),
                "source": "api",
                "refreshed_at": now,
            }
            for m in models.data
        ]
        return await _upsert(db, rows)
    except Exception as exc:
        logger.warning("sync_claude failed (%s); seeding fallback", exc)
        return await _seed_provider(db, "claude")


async def sync_all() -> dict[str, int]:
    async with AsyncSessionLocal() as db:
        settings = await db.get(AppSettings, 1)
        if settings is None:
            settings = AppSettings(id=1, ocr_provider="tesseract")

        results = await asyncio.gather(
            sync_gemini(db, settings),
            sync_vertex(db, settings),
            sync_openai(db, settings),
            sync_claude(db, settings),
            return_exceptions=True,
        )

        await db.commit()

    counts = {}
    for provider, result in zip(["gemini", "vertex", "openai", "claude"], results):
        counts[provider] = result if isinstance(result, int) else 0
    return counts

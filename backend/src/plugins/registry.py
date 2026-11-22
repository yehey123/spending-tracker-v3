"""Plugin registry: discovers OCR providers and categorizers via entry points."""

from __future__ import annotations

import importlib.metadata
import inspect
import logging
from typing import Any

from src.domain.services.ocr.base import AIPackagesMissing
from src.plugins.api import (
    API_VERSION,
    CategorizerLike,
    ProviderContext,
    ProviderDescriptor,
)

logger = logging.getLogger(__name__)

OCR_GROUP = "spending_tracker.ocr_providers"
CATEGORIZER_GROUP = "spending_tracker.categorizers"


class _TesseractDescriptor:
    key = "tesseract"
    label = "Tesseract (local)"
    api_version = API_VERSION
    config_fields: tuple = ()
    credit_weight = 0
    max_side = None

    def build(self, settings: Any, ctx: ProviderContext):
        from src.domain.services.ocr.tesseract import TesseractProvider

        return TesseractProvider()

    def has_credentials(self, settings: Any) -> bool:
        return False


_ocr_cache: dict[str, ProviderDescriptor] | None = None
_cat_cache: dict[str, CategorizerLike] | None = None


def reset_cache() -> None:
    global _ocr_cache, _cat_cache
    _ocr_cache = None
    _cat_cache = None


def _load_group(group: str, protocol: type) -> dict[str, Any]:
    found: dict[str, Any] = {}
    try:
        eps = importlib.metadata.entry_points(group=group)
    except Exception as exc:
        logger.warning("Plugin discovery failed for %s: %s", group, exc)
        return found
    for ep in eps:
        try:
            obj = ep.load()
            if inspect.isclass(obj):
                obj = obj()
            if not isinstance(obj, protocol):
                logger.warning(
                    "Plugin %r in %s does not satisfy %s — skipped",
                    ep.name,
                    group,
                    protocol.__name__,
                )
                continue
            if getattr(obj, "api_version", None) != API_VERSION:
                logger.warning(
                    "Plugin %r in %s has api_version=%r, core needs %d — skipped",
                    ep.name,
                    group,
                    getattr(obj, "api_version", None),
                    API_VERSION,
                )
                continue
            found[obj.key] = obj
        except Exception as exc:
            logger.warning("Plugin %r in %s failed to load (%s) — skipped", ep.name, group, exc)
    return found


def _ocr_providers() -> dict[str, ProviderDescriptor]:
    global _ocr_cache
    if _ocr_cache is None:
        loaded = _load_group(OCR_GROUP, ProviderDescriptor)
        loaded.pop("tesseract", None)  # built-in cannot be overridden
        _ocr_cache = {"tesseract": _TesseractDescriptor(), **loaded}
    return _ocr_cache


def _categorizers() -> dict[str, CategorizerLike]:
    global _cat_cache
    if _cat_cache is None:
        _cat_cache = _load_group(CATEGORIZER_GROUP, CategorizerLike)
    return _cat_cache


def available() -> dict[str, ProviderDescriptor]:
    """All installed OCR provider descriptors by key (always includes tesseract)."""
    return dict(_ocr_providers())


def get_ocr(key: str) -> ProviderDescriptor:
    """Return the descriptor for `key`; raise AIPackagesMissing if not installed."""
    desc = _ocr_providers().get(key)
    if desc is None:
        raise AIPackagesMissing(f"Provider '{key}' is not installed")
    return desc


def find_ocr(key: str) -> ProviderDescriptor | None:
    return _ocr_providers().get(key)


def get_categorizer(key: str) -> CategorizerLike | None:
    """Return the categorizer plugin for `key`, or None (memory-only categorization)."""
    return _categorizers().get(key)


def make_context(settings: Any) -> ProviderContext:
    from src.core.config import settings as cfg
    from src.core.crypto import decrypt_secret

    return ProviderContext(
        decrypt_secret=decrypt_secret,
        ollama_base_url=getattr(cfg, "ollama_base_url", None),
        max_output_tokens=getattr(settings, "max_output_tokens", None),
    )


async def sync_all_models() -> dict[str, int]:
    """Upsert model lists from every installed descriptor exposing list_models (no-op if none).

    list_models(settings, ctx) may be sync or async and returns dicts with keys
    model_id, display_name (optional), max_output_tokens (optional).
    """
    from datetime import datetime, timezone

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from src.db.session import AsyncSessionLocal
    from src.domain.models.app_settings import AppSettings
    from src.domain.models.model_cache import ModelCache

    listers = {
        k: d for k, d in _ocr_providers().items() if callable(getattr(d, "list_models", None))
    }
    if not listers:
        return {}
    counts: dict[str, int] = {}
    async with AsyncSessionLocal() as db:
        settings = await db.get(AppSettings, 1)
        if settings is None:
            settings = AppSettings(id=1, ocr_provider="tesseract")
        ctx = make_context(settings)
        now = datetime.now(timezone.utc)
        for key, desc in listers.items():
            try:
                models = desc.list_models(settings, ctx)
                if inspect.isawaitable(models):
                    models = await models
                rows = [
                    {
                        "provider": key,
                        "model_id": m["model_id"],
                        "display_name": m.get("display_name") or m["model_id"],
                        "max_output_tokens": m.get("max_output_tokens"),
                        "source": "api",
                        "refreshed_at": now,
                    }
                    for m in models or []
                ]
                if rows:
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
                counts[key] = len(rows)
            except Exception as exc:
                logger.warning("list_models failed for %s: %s", key, exc)
                counts[key] = 0
        await db.commit()
    return counts

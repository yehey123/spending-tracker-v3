"""AI-powered transaction categorizer with multi-provider support."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.merchant_memory import MerchantCategoryMemory
from src.domain.models.transaction_flag import TransactionFlag

if TYPE_CHECKING:
    from src.domain.models.app_settings import AppSettings
    from src.domain.models.category import Category
    from src.domain.models.transaction import Transaction

logger = logging.getLogger(__name__)

try:
    import anthropic as _anthropic_lib
except ImportError:
    _anthropic_lib = None  # type: ignore

try:
    import openai as _openai_lib
except ImportError:
    _openai_lib = None  # type: ignore


def _normalize(desc: str) -> str:
    lowered = desc.lower()
    cleaned = re.sub(r'[^a-z0-9 ]', ' ', lowered)
    return re.sub(r'\s+', ' ', cleaned).strip()


def _has_ai_credentials(settings: AppSettings) -> bool:
    p = getattr(settings, 'ai_provider', 'anthropic')
    return {
        'anthropic': bool(getattr(settings, 'anthropic_api_key', None)),
        'openai':    bool(getattr(settings, 'openai_api_key', None)),
        'gemini':    bool(getattr(settings, 'gemini_api_key', None)),
        'vertex':    bool(getattr(settings, 'google_project_id', None)),
        'local':     bool(getattr(settings, 'ai_api_url', None)),
    }.get(p, False)


class CategorizerService:
    async def categorize_statement(
        self,
        statement_id: int,
        transactions: list[Transaction],
        db: AsyncSession,
        settings: AppSettings,
        account_type: str | None = None,
    ) -> None:
        auto_threshold = getattr(settings, 'ai_category_confidence_auto', 0.85) or 0.85
        suggest_threshold = getattr(settings, 'ai_category_confidence_suggest', 0.6) or 0.6

        cats_result = await db.execute(
            select(__import__('src.domain.models.category', fromlist=['Category']).Category)
        )
        categories: list[Category] = cats_result.scalars().all()

        unknown: list[tuple[Transaction, str]] = []
        for tx in transactions:
            key = _normalize(tx.description)
            mem = await db.get(MerchantCategoryMemory, key)
            if mem and mem.confidence is not None and mem.confidence >= auto_threshold:
                tx.category_id = mem.category_id
            else:
                unknown.append((tx, key))

        if unknown and _has_ai_credentials(settings):
            merchant_names = [key for _, key in unknown]
            ai_results = await self._call_ai(merchant_names, categories, settings, account_type)

            result_map: dict[str, dict] = {r['merchant']: r for r in ai_results}

            for tx, key in unknown:
                r = result_map.get(key)
                if r is None:
                    continue
                confidence: float = r.get('confidence', 0.0)
                cat_id: int | None = r.get('category_id')

                if confidence >= auto_threshold and cat_id is not None:
                    tx.category_id = cat_id
                    await self._upsert_memory(key, cat_id, confidence, 'ai', db)
                elif confidence >= suggest_threshold and cat_id is not None:
                    flag = TransactionFlag(
                        transaction_id=tx.id,
                        flag_type='category_suggestion',
                        status='open',
                        flag_metadata={
                            'suggested_category_id': cat_id,
                            'confidence': confidence,
                            'merchant_key': key,
                        },
                    )
                    db.add(flag)

        await db.flush()

    async def _call_ai(
        self,
        merchants: list[str],
        categories: list[Category],
        settings: AppSettings,
        account_type: str | None = None,
    ) -> list[dict]:
        provider = getattr(settings, 'ai_provider', 'anthropic')
        try:
            cat_list = [{'id': c.id, 'name': c.name} for c in categories]
            _acct_line = f"Account type: {account_type}\n\n" if account_type else ""
            prompt = (
                f"Given these categories: {json.dumps(cat_list)}\n\n"
                f"{_acct_line}"
                f"Classify each merchant into the best category. "
                f"Return a JSON array: "
                f'[{{"merchant": "...", "category_id": <int or null>, "confidence": <0-1>}}]\n\n'
                f"Merchants: {json.dumps(merchants)}\n\n"
                "Return only the JSON array, no explanation."
            )

            if provider == 'anthropic':
                if _anthropic_lib is None:
                    return []
                api_key = getattr(settings, 'anthropic_api_key', None)
                model = getattr(settings, 'ai_model', None) or 'claude-haiku-4-5-20251001'
                client = _anthropic_lib.Anthropic(api_key=api_key)
                message = client.messages.create(
                    model=model,
                    max_tokens=1024,
                    messages=[{'role': 'user', 'content': prompt}],
                )
                text = message.content[0].text.strip()

            elif provider == 'openai':
                if _openai_lib is None:
                    return []
                api_key = getattr(settings, 'openai_api_key', None)
                model = getattr(settings, 'ai_model', None) or 'gpt-4o-mini'
                client = _openai_lib.OpenAI(api_key=api_key)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{'role': 'user', 'content': prompt}],
                    max_tokens=1024,
                )
                text = resp.choices[0].message.content.strip()

            elif provider == 'gemini':
                if _openai_lib is None:
                    return []
                api_key = getattr(settings, 'gemini_api_key', None)
                model = getattr(settings, 'ai_model', None) or 'gemini-2.0-flash'
                client = _openai_lib.OpenAI(
                    api_key=api_key,
                    base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
                )
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{'role': 'user', 'content': prompt}],
                    max_tokens=1024,
                )
                text = resp.choices[0].message.content.strip()

            elif provider == 'vertex':
                if _openai_lib is None:
                    return []
                import google.auth
                import google.auth.transport.requests as _google_requests
                creds, _ = google.auth.default(
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
                creds.refresh(_google_requests.Request())
                project = getattr(settings, 'google_project_id', None)
                location = getattr(settings, 'google_location', None) or 'us-central1'
                base_url = (
                    f'https://{location}-aiplatform.googleapis.com/v1beta1/projects/'
                    f'{project}/locations/{location}/endpoints/openapi/'
                )
                _raw_model = getattr(settings, 'ai_model', None) or 'google/gemini-2.5-flash'
                model = _raw_model if '/' in _raw_model else f'google/{_raw_model}'
                client = _openai_lib.OpenAI(api_key=creds.token, base_url=base_url)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{'role': 'user', 'content': prompt}],
                    max_tokens=1024,
                )
                text = resp.choices[0].message.content.strip()

            elif provider == 'local':
                if _openai_lib is None:
                    return []
                api_url = getattr(settings, 'ai_api_url', None)
                model = getattr(settings, 'ai_model', None) or 'llama3'
                client = _openai_lib.OpenAI(api_key='local', base_url=api_url)
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{'role': 'user', 'content': prompt}],
                    max_tokens=1024,
                )
                text = resp.choices[0].message.content.strip()

            else:
                logger.warning('Unknown AI provider: %s', provider)
                return []

            return json.loads(text)

        except Exception as exc:
            logger.warning('Categorizer AI call failed (%s): %s', provider, exc)
            return []

    async def _upsert_memory(
        self,
        key: str,
        category_id: int | None,
        confidence: float,
        source: str,
        db: AsyncSession,
    ) -> None:
        existing = await db.get(MerchantCategoryMemory, key)
        if existing:
            existing.category_id = category_id
            existing.confidence = confidence
            existing.source = source
            existing.usage_count = (existing.usage_count or 0) + 1
        else:
            db.add(MerchantCategoryMemory(
                description_normalized=key,
                category_id=category_id,
                source=source,
                confidence=confidence,
            ))

    async def bulk_recategorize_by_merchant(
        self,
        merchant_key: str,
        category_id: int,
        db: AsyncSession,
    ) -> int:
        from src.domain.models.transaction import Transaction as Tx
        result = await db.execute(
            select(Tx).where(Tx.status == 'active', Tx.reversed_by.is_(None))
        )
        txs = result.scalars().all()
        count = 0
        for tx in txs:
            if _normalize(tx.description) == merchant_key:
                tx.category_id = category_id
                count += 1

        await self._upsert_memory(merchant_key, category_id, 1.0, 'user', db)
        await db.flush()
        return count


categorizer_service = CategorizerService()

"""Async statement processing pipeline — OCR → parse → categorize → duplicate detect."""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.app_settings import AppSettings
from src.domain.models.statement import Statement
from src.domain.models.transaction import Transaction

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None  # type: ignore

try:
    from src.domain.services.ocr.claude import ClaudeVisionProvider
    from src.domain.services.ocr.gemini_vision import GeminiVisionProvider
    from src.domain.services.ocr.openai_vision import OpenAIVisionProvider
    from src.domain.services.ocr.tesseract import TesseractProvider
    from src.domain.services.ocr.vertex_vision import VertexVisionProvider
except ImportError as e:
    logger.error('Import error: %s', e)
    TesseractProvider = None  # type: ignore
    ClaudeVisionProvider = None  # type: ignore
    OpenAIVisionProvider = None  # type: ignore
    GeminiVisionProvider = None  # type: ignore
    VertexVisionProvider = None  # type: ignore


import hashlib
import hmac
import re
from datetime import timedelta
from decimal import Decimal

CC_NUMBER_RE = re.compile(r'\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}')
BANK_ACCT_RE = re.compile(r'\b\d{10,14}\b')
_OPENING_BALANCE_RE = re.compile(r'^OPENING_BALANCE:\s*([\d,]+\.?\d*)', re.MULTILINE)


def _extract_opening_balance(raw_text: str) -> Decimal | None:
    m = _OPENING_BALANCE_RE.search(raw_text)
    if m:
        try:
            return Decimal(m.group(1).replace(',', ''))
        except Exception:
            return None
    return None


async def detect_account(raw_text: str, db: AsyncSession):
    """
    Best-effort: extract account number from OCR text, fingerprint-match or auto-create.
    Returns Account or None (non-fatal — upload proceeds without account_id).
    """
    from datetime import date as date_type
    from sqlalchemy import select
    from src.domain.models.account import Account
    from src.core.config import settings as cfg

    digits_only = re.sub(r'[\s\-]', '', raw_text)
    cc_match = CC_NUMBER_RE.search(digits_only)
    number: str | None = None
    if cc_match:
        number = re.sub(r'[\s\-]', '', cc_match.group())
    else:
        bank_match = BANK_ACCT_RE.search(raw_text)
        if bank_match:
            number = bank_match.group()

    if not number:
        return None

    secret = cfg.app_secret
    if not secret or len(secret) < 32:
        return None

    last_four = number[-4:]
    fingerprint = hmac.new(
        secret.encode(), number.encode(), hashlib.sha256
    ).hexdigest()

    result = await db.execute(
        select(Account).where(
            Account.fingerprint == fingerprint,
            Account.is_active == True,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    new_account = Account(
        name=f"****{last_four}",
        type='credit_card',
        currency='PHP',
        last_four=last_four,
        fingerprint=fingerprint,
        opening_balance=0,
    )
    db.add(new_account)
    await db.flush()
    return new_account


async def _detect_duplicates(
    new_transactions: list[Transaction], account_id: int, db: AsyncSession
) -> None:
    """Flag suspected duplicates: same account + amount + direction within ±3 days."""
    from sqlalchemy import select
    from src.domain.models.transaction_flag import TransactionFlag

    for tx in new_transactions:
        tx_date = tx.date.replace(tzinfo=None) if tx.date.tzinfo else tx.date
        window_low = tx_date - timedelta(days=3)
        window_high = tx_date + timedelta(days=3)
        result = await db.execute(
            select(Transaction).where(
                Transaction.account_id == account_id,
                Transaction.amount == tx.amount,
                Transaction.direction == tx.direction,
                Transaction.id != tx.id,
                Transaction.status == 'active',
                Transaction.deleted_at.is_(None),
                Transaction.date >= window_low,
                Transaction.date <= window_high,
            )
        )
        duplicates = result.scalars().all()
        for dup in duplicates:
            tx.duplicate_status = 'suspected'
            db.add(TransactionFlag(
                transaction_id=tx.id,
                flag_type='suspected_duplicate',
                status='open',
                flag_metadata={
                    "peer_id": dup.id,
                    "days_apart": abs((tx.date - dup.date).days),
                    "amount": str(tx.amount),
                    "account_id": account_id,
                },
            ))


def _resolve_ocr(settings_row: AppSettings):
    from fastapi import HTTPException
    provider = settings_row.ocr_provider
    _max = settings_row.max_output_tokens
    if provider == "anthropic":
        if not settings_row.anthropic_api_key:
            raise HTTPException(status_code=422, detail="API key not configured for claude.")
        model = getattr(settings_row, 'ai_model', None) or "claude-sonnet-4-6"
        return ClaudeVisionProvider(api_key=settings_row.anthropic_api_key, model=model, max_tokens=_max or 4096)
    elif provider == "openai":
        if not settings_row.openai_api_key:
            raise HTTPException(status_code=422, detail="API key not configured for openai.")
        model = getattr(settings_row, 'ai_model', None) or "gpt-4o"
        return OpenAIVisionProvider(api_key=settings_row.openai_api_key, model=model, max_tokens=_max or 4096)
    elif provider == "gemini":
        if not settings_row.gemini_api_key:
            raise HTTPException(status_code=422, detail="Gemini API key not configured.")
        model = getattr(settings_row, 'ai_model', None) or "gemini-2.0-flash"
        return GeminiVisionProvider(api_key=settings_row.gemini_api_key, model=model, max_tokens=_max or 8192)
    elif provider == "vertex":
        if not settings_row.google_project_id:
            raise HTTPException(status_code=422, detail="Google Project ID not configured for Vertex AI.")
        location = getattr(settings_row, 'google_location', None) or "us-central1"
        model = getattr(settings_row, 'ai_model', None) or "google/gemini-2.5-flash"
        return VertexVisionProvider(project_id=settings_row.google_project_id,
                                    location=location, model=model, max_tokens=_max or 8192)
    return TesseractProvider()


class StatementPipeline:
    """Multi-stage statement processing pipeline."""

    async def run(self, statement: Statement, content: bytes, content_type: str,
                  db: AsyncSession, account_id: int | None = None) -> tuple[list[Transaction], bool]:
        """Run OCR → parse → (categorize) → staged insert. Returns (transactions, account_created)."""
        from src.domain.services.pdf_parser import extract_pdf_text
        from src.domain.services.preprocessor import preprocess
        from src.domain.services.statement_parser import parse_statement

        settings = await db.get(AppSettings, 1)
        if settings is None:
            from src.domain.models.app_settings import AppSettings as AS
            from src.core.config import settings as _cfg
            settings = AS(
                id=1,
                ocr_provider=_cfg.ocr_provider,
                anthropic_api_key=_cfg.anthropic_api_key,
                openai_api_key=_cfg.openai_api_key,
                gemini_api_key=_cfg.gemini_api_key,
            )

        ocr_provider = _resolve_ocr(settings)
        statement.ocr_provider = settings.ocr_provider
        inferred_type = "pdf" if content_type == "application/pdf" else "image"
        dev_mode = getattr(settings, 'dev_mode', False)

        file_hash = hashlib.sha256(content).hexdigest()
        statement.file_hash = file_hash

        from sqlalchemy import select as _sel
        from src.domain.models.category import Category as _Category
        prior = (await db.execute(
            _sel(Statement)
            .where(
                Statement.file_hash == file_hash,
                Statement.id != statement.id,
                Statement.status.notin_(["ocr_failed", "parse_failed", "failed", "discarded"]),
            )
            .order_by(Statement.id.desc())
            .limit(1)
        )).scalar_one_or_none()

        # Load categories once — passed to AI OCR providers for bundled categorization
        cat_rows = (await db.execute(_sel(_Category))).scalars().all()
        categories_list = [{"id": c.id, "name": c.name} for c in cat_rows]
        cat_by_name = {c.name.lower(): c.id for c in cat_rows}

        # Whether to bundle categorization into the OCR call
        bundle_categories = (
            ocr_provider.supports_categories
            and not dev_mode
            and bool(categories_list)
        )

        raw_text: str | None = None
        if prior and prior.raw_ocr_text:
            logger.info("OCR cache hit file_hash=%s (reusing statement %d)", file_hash, prior.id)
            raw_text = prior.raw_ocr_text
            statement.raw_ocr_text = raw_text
            await db.flush()

        # Stage 1 — OCR
        if raw_text is None:
            try:
                if inferred_type == "pdf":
                    raw_text = await extract_pdf_text(
                        content, ocr_provider,
                        categories=categories_list if bundle_categories else None,
                    )
                else:
                    if PILImage is None:
                        raise RuntimeError("Pillow is required for image processing.")
                    img = PILImage.open(io.BytesIO(content))
                    # Preprocessing (grayscale + threshold) helps Tesseract but hurts
                    # AI vision models — send the original color image to those.
                    if settings.ocr_provider == "tesseract":
                        img = preprocess(img)
                    MAX_SIDE = 1536
                    if settings.ocr_provider != "tesseract":
                        w, h = img.size
                        if max(w, h) > MAX_SIDE:
                            scale = MAX_SIDE / max(w, h)
                            img = img.resize((int(w * scale), int(h * scale)), PILImage.LANCZOS)
                    if bundle_categories:
                        raw_text = await ocr_provider.extract_with_categories(img, categories_list)  # type: ignore
                    else:
                        raw_text = await ocr_provider.extract_text(img)  # type: ignore

                statement.raw_ocr_text = raw_text
                logger.info(
                    "OCR complete [provider=%s] [bundled_categories=%s] [chars=%d]\n--- OCR OUTPUT ---\n%s\n--- END OCR ---",
                    settings.ocr_provider, bundle_categories, len(raw_text or ""), raw_text or "(empty)"
                )
                await db.flush()
            except Exception as e:
                statement.status = 'ocr_failed'
                statement.error_message = str(e)
                await db.flush()
                return [], False

        # Stage 1.5 — Account detection (non-fatal)
        account_created = False
        account = None
        if account_id is not None:
            # Explicit account selected by user — skip auto-detect
            from src.domain.models.account import Account
            account = await db.get(Account, account_id)
            if account:
                statement.account_id = account_id
            else:
                logger.warning('Explicit account_id=%d not found — falling back to auto-detect', account_id)
                account_id = None
        if account_id is None:
            try:
                account = await detect_account(raw_text, db)
                account_id = account.id if account else None
                if account_id is not None:
                    account_created = account.name.startswith('****')
                    statement.account_id = account_id
            except Exception as e:
                logger.warning('Account detection failed: %s', e)
                account = None
                account_id = None

        # Stage 1.55 — Store extracted opening balance on statement for user confirmation at review
        opening_balance = _extract_opening_balance(raw_text)
        if opening_balance is not None:
            statement.extracted_opening_balance = opening_balance
            logger.info('Extracted opening_balance=%.2f from statement %d (pending user confirmation)', opening_balance, statement.id)

        # If linked account is a credit card, upgrade statement_kind automatically
        if account and getattr(account, 'type', None) == 'credit_card':
            statement.statement_kind = 'credit_card'

        # Stage 1.6 — Broker branch: investment statement parsing (returns early)
        if account and account.type == 'broker':
            from src.domain.services.investment_parser import parse_investment_rows
            from src.domain.models.investment_transaction import InvestmentTransaction
            from datetime import date as date_type

            parsed_rows, parse_errors = parse_investment_rows(raw_text)
            for row in parsed_rows:
                inv = InvestmentTransaction(
                    account_id=account.id,
                    statement_id=statement.id,
                    date=date_type.today(),
                    symbol=row.symbol,
                    shares=row.shares,
                    price_per_share=row.price,
                    amount=row.amount,
                    direction=row.direction,
                    commission=row.commission,
                )
                db.add(inv)

            statement.parse_errors = parse_errors if parse_errors else None
            statement.status = 'committed'
            await db.flush()
            return [], account_created

        # Stage 2 — Parse
        try:
            parsed_rows = parse_statement(raw_text)
            logger.info("Parse complete: %d rows from %d OCR chars", len(parsed_rows), len(raw_text or ""))
            statement.parse_errors = None
        except Exception as e:
            statement.status = 'parse_failed'
            statement.error_message = str(e)
            await db.flush()
            return [], False

        # Flip directions for credit card statements (bank says CREDIT = charge to you)
        if getattr(statement, 'statement_kind', None) == 'credit_card':
            _FLIP = {'debit': 'credit', 'credit': 'debit'}
            for p in parsed_rows:
                p.direction = _FLIP.get(p.direction, p.direction)

        # Insert transactions as 'staged'
        transactions = []
        for p in parsed_rows:
            tx = Transaction(
                date=p.date,
                description=p.description,
                amount=p.amount,
                direction=p.direction,
                statement_id=statement.id,
                account_id=account_id,
                status='staged',
                transaction_origin='uploaded',
            )
            # Apply category assigned by the bundled OCR call (if any)
            if bundle_categories and p.category_name:
                cid = cat_by_name.get(p.category_name.lower())
                if cid:
                    tx.category_id = cid
            db.add(tx)
            transactions.append(tx)

        await db.flush()  # get IDs

        # Stage 3.5 — Duplicate detection (if account detected)
        if account_id is not None:
            try:
                await _detect_duplicates(transactions, account_id, db)
            except Exception as e:
                logger.warning('Duplicate detection failed: %s', e)

        # Stage 3 — AI categorization for any transactions not already categorized by OCR
        if dev_mode:
            logger.info("dev_mode=True — skipping AI categorisation")
        else:
            from src.domain.services.categorizer import _has_ai_credentials, categorizer_service
            uncategorized = [tx for tx in transactions if tx.category_id is None]
            if uncategorized and _has_ai_credentials(settings):
                try:
                    await categorizer_service.categorize_statement(
                        statement.id, uncategorized, db, settings,
                        account_type=account.type if account else None,
                    )
                except Exception as e:
                    logger.warning('Categorizer failed: %s', e)

        # Stage 4 — Final state
        review_before_commit = getattr(settings, 'review_before_commit', True)
        if review_before_commit:
            statement.status = 'staged'
        else:
            statement.status = 'committed'
            for tx in transactions:
                tx.status = 'active'

        await db.flush()
        return transactions, account_created


statement_pipeline = StatementPipeline()

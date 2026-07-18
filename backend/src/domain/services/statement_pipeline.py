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
    from src.domain.services.ocr.openai_vision import OpenAIVisionProvider
    from src.domain.services.ocr.tesseract import TesseractProvider
except ImportError as e:
    logger.error('Import error: %s', e)
    TesseractProvider = None  # type: ignore
    ClaudeVisionProvider = None  # type: ignore
    OpenAIVisionProvider = None  # type: ignore


def _resolve_ocr(settings_row: AppSettings):
    from fastapi import HTTPException
    provider = settings_row.ocr_provider
    if provider == "claude":
        if not settings_row.anthropic_api_key:
            raise HTTPException(status_code=422, detail="API key not configured for claude.")
        return ClaudeVisionProvider(api_key=settings_row.anthropic_api_key)
    elif provider == "openai":
        if not settings_row.openai_api_key:
            raise HTTPException(status_code=422, detail="API key not configured for openai.")
        return OpenAIVisionProvider(api_key=settings_row.openai_api_key)
    return TesseractProvider()


class StatementPipeline:
    """Multi-stage statement processing pipeline."""

    async def run(self, statement: Statement, content: bytes, content_type: str,
                  db: AsyncSession) -> list[Transaction]:
        """Run OCR → parse → (categorize) → staged insert. Returns list of transactions."""
        from src.domain.services.pdf_parser import extract_pdf_text
        from src.domain.services.preprocessor import preprocess
        from src.domain.services.statement_parser import parse_statement

        settings = await db.get(AppSettings, 1)
        if settings is None:
            from src.domain.models.app_settings import AppSettings as AS
            settings = AS(id=1, ocr_provider="tesseract")

        ocr_provider = _resolve_ocr(settings)
        inferred_type = "pdf" if content_type == "application/pdf" else "image"

        # Stage 1 — OCR
        try:
            if inferred_type == "pdf":
                raw_text = await extract_pdf_text(content, ocr_provider)
            else:
                if PILImage is None:
                    raise RuntimeError("Pillow is required for image processing.")
                img = PILImage.open(io.BytesIO(content))
                img = preprocess(img)
                raw_text = await ocr_provider.extract_text(img)  # type: ignore

            statement.raw_ocr_text = raw_text
            await db.flush()
        except Exception as e:
            statement.status = 'ocr_failed'
            statement.error_message = str(e)
            await db.flush()
            return []

        # Stage 2 — Parse
        try:
            parsed_rows = parse_statement(raw_text)
            statement.parse_errors = None
        except Exception as e:
            statement.status = 'parse_failed'
            statement.error_message = str(e)
            await db.flush()
            return []

        # Insert transactions as 'staged'
        transactions = []
        for p in parsed_rows:
            tx = Transaction(
                date=p.date,
                description=p.description,
                amount=p.amount,
                direction=p.direction,
                statement_id=statement.id,
                status='staged',
                transaction_origin='uploaded',
            )
            db.add(tx)
            transactions.append(tx)

        await db.flush()  # get IDs

        # Stage 3 — AI categorization (stub — runs only if API key present)
        # Stage 4 — Final state
        review_before_commit = getattr(settings, 'review_before_commit', True)
        if review_before_commit:
            statement.status = 'staged'
        else:
            statement.status = 'committed'
            for tx in transactions:
                tx.status = 'active'

        await db.flush()
        return transactions


statement_pipeline = StatementPipeline()

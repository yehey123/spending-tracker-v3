"""Statements upload, list, and delete routes."""

from __future__ import annotations

import io
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.statements import StatementOut
from src.db.session import get_db
from src.domain.models.app_settings import AppSettings
from src.domain.models.statement import Statement
from src.domain.models.transaction import Transaction
from src.domain.services.pdf_parser import extract_pdf_text
from src.domain.services.preprocessor import preprocess
from src.domain.services.statement_parser import parse_statement
from src.domain.services.storage import get_storage_backend

import logging
logger = logging.getLogger('statements')

try:
    from PIL import Image as PILImage
except ImportError:  # pragma: no cover
    PILImage = None  # type: ignore[assignment]

try:
    from src.domain.services.ocr.claude import ClaudeVisionProvider
    from src.domain.services.ocr.openai_vision import OpenAIVisionProvider
    from src.domain.services.ocr.tesseract import TesseractProvider
except ImportError as e:  # pragma: no cover
    logger.error('Error in importing: %s', e)
    TesseractProvider = None  # type: ignore[assignment]
    ClaudeVisionProvider = None  # type: ignore[assignment]
    OpenAIVisionProvider = None  # type: ignore[assignment]

router = APIRouter()

_ALLOWED_MIMES = {"image/png", "image/jpeg", "application/pdf"}
_MAX_SIZE = 20 * 1024 * 1024  # 20 MB


def _resolve_ocr(settings_row: AppSettings) -> object:
    """Instantiate the correct OCR provider from the DB settings row."""
    provider = settings_row.ocr_provider
    if provider == "claude":
        if not settings_row.anthropic_api_key:
            raise HTTPException(
                status_code=422,
                detail="API key not configured for claude.",
            )
        return ClaudeVisionProvider(api_key=settings_row.anthropic_api_key)
    elif provider == "openai":
        if not settings_row.openai_api_key:
            raise HTTPException(
                status_code=422,
                detail="API key not configured for openai.",
            )
        return OpenAIVisionProvider(api_key=settings_row.openai_api_key)
    return TesseractProvider()


@router.post("/upload", response_model=StatementOut, status_code=200)
async def upload_statement(
    file: UploadFile = File(...),
    type: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
) -> StatementOut:
    """Upload a bank statement image or PDF, run OCR pipeline, persist transactions."""
    # --- MIME validation ---
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_MIMES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Accepted: PNG, JPEG, PDF.",
        )

    # --- Read + size validation ---
    content = await file.read()
    if len(content) > _MAX_SIZE:
        raise HTTPException(status_code=400, detail="File exceeds 20 MB limit.")

    # --- Infer type ---
    inferred_type = "pdf" if content_type == "application/pdf" else "image"

    # --- Fetch settings for OCR provider ---
    settings_result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings_row = settings_result.scalar_one_or_none()
    if settings_row is None:
        # Fallback defaults if seed row missing
        settings_row = AppSettings(id=1, ocr_provider="tesseract")

    ocr_provider = _resolve_ocr(settings_row)  # raises 422 if key missing

    # --- Save file via storage backend ---
    ext = "pdf" if inferred_type == "pdf" else ("png" if content_type == "image/png" else "jpg")
    key = f"{uuid.uuid4()}.{ext}"
    storage = get_storage_backend()
    try:
        await storage.save(key, content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {e}") from e

    # --- Create Statement row ---
    statement = Statement(
        filename=file.filename or key,
        storage_key=key,
        type=inferred_type,
        status="processing",
        ocr_provider=settings_row.ocr_provider,
    )
    db.add(statement)
    await db.commit()
    await db.refresh(statement)

    # --- Run pipeline ---
    try:
        if inferred_type == "pdf":
            text = await extract_pdf_text(content, ocr_provider)
        else:
            if PILImage is None:
                raise RuntimeError("Pillow is required for image processing.")
            img = PILImage.open(io.BytesIO(content))
            img = preprocess(img)
            text = await ocr_provider.extract_text(img)  # type: ignore[attr-defined]

        parsed = parse_statement(text)
        logger.error('Parsed outputs: %s', parsed)

        # --- Bulk insert transactions ---
        for p in parsed:
            txn = Transaction(
                date=p.date,
                description=p.description,
                amount=p.amount,
                direction=p.direction,
                statement_id=statement.id,
            )
            db.add(txn)

        await db.commit()

        statement.status = "done"
        await db.commit()
        await db.refresh(statement)

    except HTTPException:
        raise
    except Exception as e:
        statement.status = "failed"
        statement.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}") from e

    status_str = (
        str(statement.status.value) if hasattr(statement.status, "value") else str(statement.status)
    )
    type_str = (
        str(statement.type.value) if hasattr(statement.type, "value") else str(statement.type)
    )
    return StatementOut(
        id=statement.id,
        filename=statement.filename,
        type=type_str,
        status=status_str,
        ocr_provider=statement.ocr_provider,
        transaction_count=len(parsed),
        uploaded_at=statement.uploaded_at,
        error_message=statement.error_message,
    )


@router.get("", response_model=list[StatementOut])
async def list_statements(
    offset: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[StatementOut]:
    """Paginated list of statements with computed transaction_count."""
    count_sq = (
        select(func.count(Transaction.id))
        .where(Transaction.statement_id == Statement.id)
        .correlate(Statement)
        .scalar_subquery()
    )
    stmt = select(Statement, count_sq.label("transaction_count")).offset(offset).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [
        StatementOut(
            **{
                **{k: v for k, v in row.Statement.__dict__.items() if not k.startswith("_")},
                "type": (
                    str(row.Statement.type.value)
                    if hasattr(row.Statement.type, "value")
                    else str(row.Statement.type)
                ),
                "status": (
                    str(row.Statement.status.value)
                    if hasattr(row.Statement.status, "value")
                    else str(row.Statement.status)
                ),
                "transaction_count": row.transaction_count or 0,
            }
        )
        for row in rows
    ]


@router.delete("/{id}", status_code=204)
async def delete_statement(id: int, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a statement and its file. Transactions get statement_id=NULL via FK cascade."""
    result = await db.execute(select(Statement).where(Statement.id == id))
    statement = result.scalar_one_or_none()
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found.")

    storage = get_storage_backend()
    if statement.storage_key:
        try:
            await storage.delete(statement.storage_key)
        except Exception:
            pass  # silent — object may already be gone

    await db.delete(statement)
    await db.commit()

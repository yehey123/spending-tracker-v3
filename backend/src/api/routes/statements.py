"""Statements upload, list, delete, and staged-review routes."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas.statements import StatementOut
from src.core.deps import get_current_user
from src.db.session import get_db
from src.domain.models.statement import Statement
from src.domain.models.transaction import Transaction
from src.domain.models.user import User
import logging
logger = logging.getLogger('statements')

router = APIRouter()

_ALLOWED_MIMES = {"image/png", "image/jpeg", "application/pdf"}
_MAX_SIZE = 20 * 1024 * 1024  # 20 MB
_CHUNK_SIZE = 1 << 20  # 1 MB

_MAGIC_BYTES: dict[str, bytes] = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
    "application/pdf": b"%PDF-",
}

# PostScript/EPS — reject before magic check regardless of declared content_type.
_EPS_MAGIC_PREFIXES: tuple[bytes, ...] = (
    b"%!PS-Adobe-",
    b"%!EPS",
    b"\xc5\xd0\xd3\xc6",  # Binary EPS header (EPSI)
)


def _is_eps_content(content: bytes) -> bool:
    return any(content.startswith(p) for p in _EPS_MAGIC_PREFIXES)


def _content_matches_declared_type(content: bytes, content_type: str) -> bool:
    """Verify the actual file bytes start with the magic number for content_type."""
    signature = _MAGIC_BYTES.get(content_type)
    if signature is None:
        return False
    return content.startswith(signature)


@router.post("/upload", response_model=StatementOut, status_code=200)
async def upload_statement(
    file: UploadFile = File(...),
    type: str | None = Form(default=None),
    statement_kind: str = Form(default="bank_account"),
    account_id: int | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StatementOut:
    """Upload a bank statement image or PDF, run OCR pipeline, persist transactions."""
    # MIME + size validation
    content_type = file.content_type or ""
    if content_type not in _ALLOWED_MIMES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Accepted: PNG, JPEG, PDF.",
        )
    buf = bytearray()
    while True:
        chunk = await file.read(_CHUNK_SIZE)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > _MAX_SIZE:
            raise HTTPException(status_code=400, detail="File exceeds 20 MB limit.")
    content = bytes(buf)

    if _is_eps_content(content):
        raise HTTPException(
            status_code=400,
            detail="PostScript/EPS files are not accepted.",
        )

    if not _content_matches_declared_type(content, content_type):
        raise HTTPException(
            status_code=400,
            detail="File content does not match its declared type.",
        )

    inferred_type = "pdf" if content_type == "application/pdf" else "image"
    ext = "pdf" if inferred_type == "pdf" else ("png" if content_type == "image/png" else "jpg")
    statement = Statement(
        filename=file.filename or f"upload.{ext}",
        type=inferred_type,
        status="processing",
        ocr_provider="tesseract",  # will be updated by pipeline
        statement_kind=statement_kind,
        user_id=current_user.id,
    )
    if type == 'receipt':
        statement.file_type = 'receipt'
    db.add(statement)
    await db.commit()
    await db.refresh(statement)

    try:
        from src.domain.services.statement_pipeline import statement_pipeline
        transactions, account_created = await statement_pipeline.run(
            statement, content, content_type, db, account_id=account_id, user_id=current_user.id
        )
        await db.commit()
        await db.refresh(statement)
    except HTTPException:
        raise
    except Exception as e:
        statement.status = "failed"
        statement.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}") from e

    status_str = str(statement.status.value) if hasattr(statement.status, "value") else str(statement.status)
    type_str = str(statement.type.value) if hasattr(statement.type, "value") else str(statement.type)
    return StatementOut(
        id=statement.id,
        filename=statement.filename,
        type=type_str,
        status=status_str,
        ocr_provider=statement.ocr_provider,
        transaction_count=len(transactions),
        uploaded_at=statement.uploaded_at,
        error_message=statement.error_message,
        account_id=statement.account_id,
        account_created=account_created,
    )


@router.get("", response_model=list[StatementOut])
async def list_statements(
    offset: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[StatementOut]:
    """Paginated list of statements with computed transaction_count."""
    count_sq = (
        select(func.count(Transaction.id))
        .where(Transaction.statement_id == Statement.id)
        .correlate(Statement)
        .scalar_subquery()
    )
    stmt = (
        select(Statement, count_sq.label("transaction_count"))
        .where(Statement.user_id == current_user.id)
        .offset(offset)
        .limit(limit)
    )
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


@router.get("/{statement_id}/staged")
async def get_staged_transactions(
    statement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all staged transactions for a statement pending review."""
    result = await db.execute(
        select(Statement).where(Statement.id == statement_id, Statement.user_id == current_user.id)
    )
    stmt = result.scalar_one_or_none()
    if stmt is None:
        raise HTTPException(status_code=404, detail="Statement not found.")

    result = await db.execute(
        select(Transaction)
        .where(Transaction.statement_id == statement_id, Transaction.status == 'staged')
        .order_by(Transaction.date.asc())
    )
    transactions = result.scalars().all()

    # Compute extracted total (sum of debit staged transactions)
    debit_total = sum(tx.amount for tx in transactions if tx.direction in ('debit', 'DEBIT'))
    debit_total_str = str(debit_total)

    return {
        "statement_id": statement_id,
        "declared_total": str(stmt.declared_total) if stmt.declared_total else None,
        "extracted_total": debit_total_str,
        "total_match": stmt.declared_total is not None and abs(stmt.declared_total - debit_total) < 1,
        "extracted_opening_balance": str(stmt.extracted_opening_balance) if stmt.extracted_opening_balance is not None else None,
        "account_id": stmt.account_id,
        "transactions": [
            {
                "id": tx.id,
                "date": tx.date.isoformat() if tx.date else None,
                "description": tx.description,
                "amount": str(tx.amount),
                "direction": tx.direction if isinstance(tx.direction, str) else tx.direction.value,
                "category_id": tx.category_id,
                "currency": tx.currency,
            }
            for tx in transactions
        ],
    }


class CommitBody(BaseModel):
    opening_balance: Decimal | None = None


@router.post("/{statement_id}/commit")
async def commit_statement(
    statement_id: int,
    body: CommitBody = CommitBody(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Promote all staged transactions to active. Optionally set account opening_balance."""
    result = await db.execute(
        select(Statement).where(Statement.id == statement_id, Statement.user_id == current_user.id)
    )
    stmt = result.scalar_one_or_none()
    if stmt is None:
        raise HTTPException(status_code=404, detail="Statement not found.")
    status_val = stmt.status.value if hasattr(stmt.status, 'value') else stmt.status
    if status_val != 'staged':
        raise HTTPException(status_code=409, detail="Statement is not in staged state")

    if body.opening_balance is not None and stmt.account_id is not None:
        from src.domain.models.account import Account
        account = await db.get(Account, stmt.account_id)
        if account:
            account.opening_balance = body.opening_balance

    await db.execute(
        update(Transaction)
        .where(Transaction.statement_id == statement_id, Transaction.status == 'staged')
        .values(status='active')
    )
    stmt.status = 'committed'
    await db.commit()
    return {"committed": statement_id}


@router.post("/{statement_id}/discard")
async def discard_statement(
    statement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete all staged transactions and mark statement as discarded."""
    result = await db.execute(
        select(Statement).where(Statement.id == statement_id, Statement.user_id == current_user.id)
    )
    stmt = result.scalar_one_or_none()
    if stmt is None:
        raise HTTPException(status_code=404, detail="Statement not found.")
    status_val = stmt.status.value if hasattr(stmt.status, 'value') else stmt.status
    if status_val != 'staged':
        raise HTTPException(status_code=409, detail="Statement is not in staged state")

    await db.execute(
        delete(Transaction)
        .where(Transaction.statement_id == statement_id, Transaction.status == 'staged')
    )
    stmt.status = 'discarded'
    await db.commit()
    return {"discarded": statement_id}


@router.post("/{statement_id}/flip-directions")
async def flip_statement_directions(
    statement_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Flip DEBIT↔CREDIT on all staged transactions for a statement."""
    result = await db.execute(
        select(Statement).where(Statement.id == statement_id, Statement.user_id == current_user.id)
    )
    stmt = result.scalar_one_or_none()
    if stmt is None:
        raise HTTPException(status_code=404, detail="Statement not found.")
    status_val = stmt.status.value if hasattr(stmt.status, 'value') else stmt.status
    if status_val != 'staged':
        raise HTTPException(status_code=409, detail="Statement is not in staged state")

    from sqlalchemy import Enum, case, cast, literal
    _dir_enum = Enum("debit", "credit", name="transaction_direction")
    result = await db.execute(
        update(Transaction)
        .where(Transaction.statement_id == statement_id, Transaction.status == 'staged')
        .values(direction=case(
            (Transaction.direction == 'debit', cast(literal('credit'), _dir_enum)),
            else_=cast(literal('debit'), _dir_enum),
        ))
        .returning(Transaction.id)
    )
    flipped = len(result.all())
    await db.commit()
    return {"flipped": flipped}


@router.delete("/{id}", status_code=204)
async def delete_statement(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a statement and its file. Transactions get statement_id=NULL via FK cascade."""
    result = await db.execute(
        select(Statement).where(Statement.id == id, Statement.user_id == current_user.id)
    )
    statement = result.scalar_one_or_none()
    if statement is None:
        raise HTTPException(status_code=404, detail="Statement not found.")

    await db.delete(statement)
    await db.commit()

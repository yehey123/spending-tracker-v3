"""E11 invite gate endpoints.

Public routes (no require_token):
  POST /request-access              — submit an access request
  GET  /admin/approve/{id}?sig=...  — operator approves (HMAC-gated)
  GET  /admin/deny/{id}?sig=...     — operator denies  (HMAC-gated)
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.email import (
    generate_invite_token,
    invite_expires_at,
    make_hmac_sig,
    send_operator_request_email,
    send_user_invite_email,
    verify_hmac_sig,
)
from src.db.session import get_db
from src.domain.models.access_request import AccessRequest
from src.domain.models.invite_token import InviteToken

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AccessRequestCreate(BaseModel):
    email: EmailStr
    reason: str | None = None


class AccessRequestResponse(BaseModel):
    id: str
    email: str
    status: str
    message: str


# ---------------------------------------------------------------------------
# POST /request-access
# ---------------------------------------------------------------------------

@router.post("/request-access", response_model=AccessRequestResponse, status_code=202)
async def request_access(
    body: AccessRequestCreate,
    db: AsyncSession = Depends(get_db),
) -> AccessRequestResponse:
    """Submit an access request.

    Saves an access_requests row and emails the operator. If the email fails the
    row is rolled back and a 502 is returned so the frontend can surface the error
    rather than silently swallowing a mis-configured mail server.
    """
    req = AccessRequest(
        email=str(body.email),
        reason=body.reason,
        status="pending",
    )
    db.add(req)

    try:
        await db.flush()  # get req.id without committing
        await send_operator_request_email(
            operator_email=settings.smtp_user,
            request_id=req.id,
            applicant_email=req.email,
            reason=req.reason,
            base_url=settings.app_base_url,
        )
        await db.commit()
        await db.refresh(req)
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception("Email delivery failed for access request from %s.", body.email)
        raise HTTPException(
            status_code=502,
            detail="Unable to send notification email. Please try again later or contact the administrator.",
        )

    return AccessRequestResponse(
        id=req.id,
        email=req.email,
        status=req.status,
        message="Your request has been received. You will receive an email if approved.",
    )


# ---------------------------------------------------------------------------
# GET /admin/approve/{request_id}
# ---------------------------------------------------------------------------

@router.get("/admin/approve/{request_id}")
async def admin_approve(
    request_id: str,
    sig: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Approve an access request and send an invite email.

    Idempotent: if already approved, returns 200 with a note.
    HMAC signature validated against 'approve:{request_id}'.
    """
    if not verify_hmac_sig(f"approve:{request_id}", sig):
        raise HTTPException(status_code=403, detail="Invalid or expired signature.")

    req = await db.get(AccessRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Access request not found.")

    if req.status == "approved":
        return {"status": "already_approved", "email": req.email}

    if req.status == "denied":
        return {
            "status": "already_denied",
            "message": "This request was already denied. Approve is a no-op.",
        }

    # Commit approval status first — this is idempotent state, always safe to persist.
    req.status = "approved"
    await db.commit()

    # Generate token but hold in session — only commit after email succeeds.
    raw_token, token_hash = generate_invite_token()
    expires_at = invite_expires_at()
    db.add(InviteToken(token_hash=token_hash, email=req.email, expires_at=expires_at, consumed_at=None))

    try:
        await send_user_invite_email(
            to_email=req.email,
            raw_token=raw_token,
            expires_at=expires_at,
            base_url=settings.app_base_url,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception(
            "Access request %s approved but invite email failed for %s — token not saved.",
            request_id,
            req.email,
        )
        raise HTTPException(
            status_code=502,
            detail="Request approved but invite email could not be sent. Use resend-invite to retry once the mail server is fixed.",
        )

    return {"status": "approved", "email": req.email}


# ---------------------------------------------------------------------------
# GET /admin/deny/{request_id}
# ---------------------------------------------------------------------------

@router.get("/admin/deny/{request_id}")
async def admin_deny(
    request_id: str,
    sig: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Deny an access request.

    Idempotent: if already denied or approved, returns 200 with a note.
    HMAC signature validated against 'deny:{request_id}'.
    """
    if not verify_hmac_sig(f"deny:{request_id}", sig):
        raise HTTPException(status_code=403, detail="Invalid or expired signature.")

    req = await db.get(AccessRequest, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Access request not found.")

    if req.status == "denied":
        return {"status": "already_denied", "email": req.email}

    if req.status == "approved":
        return {
            "status": "already_approved",
            "message": "This request was already approved. Deny is a no-op.",
        }

    req.status = "denied"
    await db.commit()

    return {"status": "denied", "email": req.email}

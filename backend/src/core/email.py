"""Transactional email via Gmail SMTP (aiosmtplib).

Provides:
  - send_operator_request_email  — notify operator of a new access request
  - send_user_invite_email       — send invite link to approved applicant
  - make_hmac_sig / verify_hmac_sig  — HMAC-SHA-256 helpers for admin links
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from src.core.config import settings

# ---------------------------------------------------------------------------
# HMAC helpers
# ---------------------------------------------------------------------------

def _hmac_key() -> bytes:
    """Return the active HMAC key bytes.

    Prefers settings.jwt_secret; falls back to settings.app_secret.
    Raises RuntimeError when both are empty (configuration error).
    """
    raw = settings.jwt_secret or settings.app_secret
    if not raw:
        raise RuntimeError(
            "HMAC key is not configured. Set JWT_SECRET (or APP_SECRET) in the environment."
        )
    return raw.encode()


def make_hmac_sig(message: str) -> str:
    """Return a hex HMAC-SHA-256 signature for *message*."""
    return hmac.new(_hmac_key(), message.encode(), "sha256").hexdigest()


def verify_hmac_sig(message: str, sig: str) -> bool:
    """Return True when *sig* is a valid signature for *message* (constant-time)."""
    expected = make_hmac_sig(message)
    return hmac.compare_digest(expected, sig)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def generate_invite_token() -> tuple[str, str]:
    """Return (raw_token, sha256_hash).

    Store only the hash in the database; send the raw token to the user.
    """
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return raw, digest


def invite_expires_at() -> datetime:
    """Return UTC expiry timestamp 7 days from now."""
    return datetime.now(timezone.utc) + timedelta(days=7)


# ---------------------------------------------------------------------------
# SMTP send
# ---------------------------------------------------------------------------

async def _send(subject: str, to: str, plain: str, html: str) -> None:
    """Send a single email via Gmail SMTP (STARTTLS on port 587).

    When smtp_user is unset (local dev), prints to stdout instead of sending.
    Raises aiosmtplib.SMTPException on delivery failure.
    """
    if not settings.smtp_user:
        import sys
        print(
            f"\n[EMAIL] To: {to}\nSubject: {subject}\n{plain}",
            file=sys.stdout,
            flush=True,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_user
    msg["To"] = to
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )


# ---------------------------------------------------------------------------
# Operator notification email (sent after POST /request-access)
# ---------------------------------------------------------------------------

def _operator_notification_plain(
    request_id: str,
    email: str,
    reason: str | None,
    approve_url: str,
    deny_url: str,
) -> str:
    reason_line = f"Reason: {reason}" if reason else "No reason provided."
    return f"""\
New access request received.

Email:   {email}
{reason_line}

To approve and send an invite link, visit:
{approve_url}

To deny this request, visit:
{deny_url}

These links are single-action (idempotent — safe to click more than once).
Request ID: {request_id}
"""


def _operator_notification_html(
    request_id: str,
    email: str,
    reason: str | None,
    approve_url: str,
    deny_url: str,
) -> str:
    reason_display = reason if reason else "<em>No reason provided.</em>"
    return f"""\
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <h2>New Access Request</h2>
  <table>
    <tr><td><strong>Email:</strong></td><td>{email}</td></tr>
    <tr><td><strong>Reason:</strong></td><td>{reason_display}</td></tr>
    <tr><td><strong>Request ID:</strong></td><td><code>{request_id}</code></td></tr>
  </table>
  <p style="margin-top:24px">
    <a href="{approve_url}"
       style="background:#16a34a;color:#fff;padding:10px 20px;
              text-decoration:none;border-radius:4px;margin-right:12px">
      ✅ Approve &amp; Send Invite
    </a>
    <a href="{deny_url}"
       style="background:#dc2626;color:#fff;padding:10px 20px;
              text-decoration:none;border-radius:4px">
      ❌ Deny
    </a>
  </p>
  <p style="color:#6b7280;font-size:12px">
    These links are idempotent — safe to click more than once.<br>
    Request ID: {request_id}
  </p>
</body>
</html>
"""


async def send_operator_request_email(
    operator_email: str,
    request_id: str,
    applicant_email: str,
    reason: str | None,
    base_url: str,
) -> None:
    """Email the operator about a new access request."""
    approve_sig = make_hmac_sig(f"approve:{request_id}")
    deny_sig = make_hmac_sig(f"deny:{request_id}")
    approve_url = f"{base_url}/admin/approve/{request_id}?sig={approve_sig}"
    deny_url = f"{base_url}/admin/deny/{request_id}?sig={deny_sig}"

    plain = _operator_notification_plain(
        request_id, applicant_email, reason, approve_url, deny_url
    )
    html = _operator_notification_html(
        request_id, applicant_email, reason, approve_url, deny_url
    )
    await _send(
        subject=f"[Spending Tracker] Access request from {applicant_email}",
        to=operator_email,
        plain=plain,
        html=html,
    )


# ---------------------------------------------------------------------------
# Invite email (sent to applicant after operator approves)
# ---------------------------------------------------------------------------

def _invite_plain(invite_url: str, expires_at: datetime) -> str:
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M UTC")
    return f"""\
You have been approved to access Spending Tracker!

Click the link below to set up your account. The link expires on {expires_str}.

{invite_url}

If you did not request access, you can ignore this email.
"""


def _invite_html(invite_url: str, expires_at: datetime) -> str:
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M UTC")
    return f"""\
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <h2>You're approved!</h2>
  <p>Click the button below to set up your Spending Tracker account.</p>
  <p>
    <a href="{invite_url}"
       style="background:#2563eb;color:#fff;padding:12px 24px;
              text-decoration:none;border-radius:4px;display:inline-block">
      Accept Invite &amp; Create Account
    </a>
  </p>
  <p style="color:#6b7280;font-size:12px">
    This link expires on {expires_str}.<br>
    If you did not request access, you can ignore this email.
  </p>
</body>
</html>
"""


async def send_user_invite_email(
    to_email: str,
    raw_token: str,
    expires_at: datetime,
    base_url: str,
) -> None:
    """Send the invite link to an approved applicant."""
    invite_url = f"{base_url}/accept-invite?token={raw_token}"
    plain = _invite_plain(invite_url, expires_at)
    html = _invite_html(invite_url, expires_at)
    await _send(
        subject="[Spending Tracker] Your invite link",
        to=to_email,
        plain=plain,
        html=html,
    )

# Security Rules — Spending Tracker SaaS

Derived from the 2026-07-29 blueprint audit (E10–E16). These rules apply to all future epics and PRs.

---

## RULE-SEC-01: Auth + isolation are always atomic

Never deploy an auth epic (login, registration, JWT issuance) and a data-isolation epic (user_id FK, RLS, route scoping) in separate windows. The gap between them is a window where any valid JWT grants access to all users' data.

**Enforcement**: Auth epics and their corresponding data-isolation migrations must be in the same PR or the same sequential deploy window with no intermediate deployments to main.

---

## RULE-SEC-02: No user_id from request body or query params

No route that returns or modifies user data may accept `user_id` as an unauthenticated query parameter or request body field. The authenticated user's identity must always come from `Depends(get_current_user)`.

**Pattern**:
```python
# CORRECT
@router.get("/credits/balance")
async def balance(current_user: User = Depends(get_current_user), ...):
    return await get_balance(current_user.id, ...)

# FORBIDDEN — IDOR vulnerability
@router.get("/credits/balance")
async def balance(user_id: uuid.UUID, ...):
    ...
```

Any route signature with `user_id: uuid.UUID` as a query or body param is an immediate code-review REJECT.

---

## RULE-SEC-03: Separate secrets for separate concerns

`JWT_SECRET` (access token signing) and `ADMIN_LINK_SECRET` (HMAC-signed email links) must be distinct env vars with independent rotation schedules. Using the same secret couples JWT token validity to admin link validity — rotating one invalidates the other.

**Required env vars in `.env.production`**:
- `JWT_SECRET` — ≥ 32 chars, used only in `core/auth.py` for HS256 signing
- `ADMIN_LINK_SECRET` — ≥ 32 chars, used only in E11's HMAC email link signing

---

## RULE-SEC-03b: Use Argon2id, not bcrypt, for new password hashing

OWASP Password Storage Cheatsheet (2025) classifies bcrypt as "legacy-only." The primary 2025 recommendation is **Argon2id (19 MiB memory, 2 iterations, parallelism=1)**.

Additionally, bcrypt silently truncates passwords at 72 bytes — users with long passphrases get weaker protection than they expect.

**Migration** (passlib supports transparent re-hashing):
```python
_pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],  # argon2 first = new hashes use argon2
    deprecated=["bcrypt"],          # existing bcrypt hashes auto-verified and re-hashed on next login
)
```

For E12: change `CryptContext(schemes=["bcrypt"])` to the above. No DB migration needed — passlib detects the hash algorithm from the stored hash prefix.

---

## RULE-SEC-04: Rate-limit all auth endpoints

`POST /auth/login`, `POST /auth/register`, and `POST /request-access` must be rate-limited to prevent credential stuffing and invite-token brute-force. Apply at the Caddy layer (preferred) or via `slowapi` in FastAPI.

**Caddy directive** (add to Caddyfile):
```caddy
@auth_routes path /auth/login /auth/register /request-access
rate_limit @auth_routes 5r/m
```

Tesseract fallback rate: unlimited (no auth needed). AI OCR endpoints: credit-gated, which provides implicit throttling.

---

## RULE-SEC-05: OAuth state must be server-tied

The Google OAuth `state` parameter must be bound to the originating session before the user is redirected to Google. Returning `state` in the JSON body for the client to pass back provides no CSRF protection.

**Correct pattern**: sign a short-lived state token server-side (e.g. `hmac(session_id + timestamp)`) and store the binding in a short-lived HTTPOnly cookie. Validate on callback by re-deriving the HMAC.

---

## RULE-SEC-05b: Admin routes need require_admin dependency, not just require_user

Any route under `/admin/` must use a `require_admin` FastAPI dependency that:
1. Calls `get_current_user` (validates JWT, checks `is_active`)
2. Checks `current_user.is_admin == True` → returns 403 if not

Never gate admin routes on a request-body `is_admin` field or on `user_id` alone. The identity comes from the JWT.

```python
async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
```

---

## RULE-SEC-05c: 401 vs 403 — get_current_user must distinguish these cases

- **401 Unauthorized**: JWT absent, expired, or cryptographically invalid. The user *can* fix this by re-authenticating. Frontend offers re-auth modal.
- **403 Forbidden**: JWT is valid but `is_active = false` (admin-deactivated account). Re-authenticating will NOT help. Frontend shows "access revoked by administrator" message without a login form.

This distinction is not cosmetic — it drives correct frontend behavior. `get_current_user` must check `is_active` after token decode and return 403 (not 401) when the user row exists but is deactivated.

---

## RULE-SEC-07: Token expiry limits

| Token | Max lifetime | Rule |
|---|---|---|
| Access token (JWT) | 15 minutes | Already correct. Add `jti` UUID claim for future blocklist support. |
| Refresh token | 30 days absolute | Add `absolute_expires_at = created_at + 30 days`. Rotation extends `expires_at` only; never extends `absolute_expires_at`. |
| Invite token | 24 hours | Reduce from 7 days. Add resend-invite endpoint for expired invites. |
| Admin approve/deny links | 48 hours | Reduce from 7 days. Links are idempotent — operator can re-approve/deny from the admin UI if link expires. |

---

## RULE-SEC-08: Session IDs in device management — never expose token_hash

The `refresh_tokens.token_hash` is a SHA-256 hash of the opaque token. It is a secret — exposing it to the frontend enables token lookup attacks.

Device management uses a separate `session_id UUID` column (added in E19) as the public handle for revocation. The frontend never sees `token_hash`.

Pattern for `DELETE /auth/sessions/{session_id}`:
```python
# Resolve internally — scope to current user prevents cross-user revocation
result = await db.execute(
    select(RefreshToken).where(
        RefreshToken.session_id == session_id,
        RefreshToken.user_id == current_user.id  # ← user scope is the guard
    )
)
```

---

## RULE-SEC-06: invite_tokens schema contract

`invite_tokens` table contract (set by E11, consumed by E12 and any future consumer):

| Column       | Type          | Notes                                    |
|---|---|---|
| `token_hash` | `TEXT PK`     | SHA-256 hex of raw token — never store raw |
| `email`      | `TEXT NOT NULL` | must match the registering email          |
| `expires_at` | `TIMESTAMPTZ NOT NULL` | 24-hour window (RULE-SEC-07)   |
| `consumed_at`| `TIMESTAMPTZ` | null = valid; set atomically on consumption |

Any consumer must: (1) hash the raw token before querying, (2) use `SELECT FOR UPDATE` to prevent TOCTOU, (3) update `consumed_at` (not `used_at` or any other name).

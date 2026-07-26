# Implementation Status — Design ↔ Code Divergence Ledger

Per the workspace divergence rule: a design↔code disagreement is never resolved silently in
either direction. Each entry records the claim, both sides with citations, the date, and status.
Running code is factual truth; the design doc is the normative record.

---

## 2026-07-26 — Security hardening batch (findings #1–#10)

Opened during a full-history security review of all 92 commits. Exit decisions taken by the
repo owner via an explicit decision gate on 2026-07-26.

### DSC-1 — "No authentication in v1" vs. auth landing
- **Design**: `design/features/spending-tracker/proposal.md` §Non-Goals — *"No multi-user or
  authentication in v1 (auth is an explicit later pivot)"*
- **Code (before)**: no auth on any of 13 routers; `grep` for auth primitives in `backend/src`
  returned only the CORS import.
- **Resolution**: (b) amend design to match the new decision. Owner chose to add an opt-in
  shared-secret layer configurable via env. Empty `API_TOKEN` preserves the documented v1
  behaviour exactly, so the non-goal is narrowed rather than reversed — multi-user stays out.
- **Status**: CLOSED — design amended, `src/core/auth.py` added.

### DSC-2 — CORS: design said env-tightenable, code hardcoded a wildcard
- **Design**: `proposal.md` §Security notes — *"CORS configured to allow all origins by default
  ... Can be tightened via env var."*
- **Code (before)**: `backend/src/main.py:44` — `allow_origins=["*"]`, no env var, no way to
  tighten. Introduced `3f464aa2`.
- **Adjudication**: this was code drift, not an accepted decision — the design already promised
  configurability that was never built. Fixing it *aligned* code to design and needed no
  amendment.
- **Additional finding**: the design's stated rationale ("self-hosted; user controls the server")
  was itself unsound. It defends against a network attacker. The live vector was a browser tab:
  with no auth, wildcard CORS let any site the user visited read `localhost` API responses
  cross-origin. Rationale corrected in the amendment, not just the code.
- **Status**: CLOSED — `CORS_ORIGINS` env var, localhost + Capacitor defaults.

### DSC-3 — Plaintext API keys accepted vs. encryption landing
- **Design**: `proposal.md` §Security notes and R6 — *"acceptable for single-user self-hosted v1;
  flag for encryption if auth is added"* / *"prioritize encryption if auth lands"*
- **Code (before)**: `app_settings.anthropic_api_key` / `openai_api_key` / `gemini_api_key`
  stored as plain columns.
- **Adjudication**: the design's own conditional fired — auth landed (DSC-1), so its stated
  trigger for encryption was met. This is the design being *followed*, not overridden.
- **Status**: CLOSED — R6 closed, new residual R12 opened (`APP_SECRET` now dual-purpose:
  fingerprints + at-rest key; rotation breaks both).

### DSC-4 — Commit message overstates its own contents
- **Claim**: `4356077c` message — *"settings.png GCP project ID field re-blurred."*
- **Reality**: `settings.png` is absent from that commit's file list and is byte-identical
  (65303 bytes) to the version at `0c18cce9`. The blur was applied at capture time, not by that
  commit.
- **Adjudication**: no code impact; recorded because the commit is part of the remediation trail
  for the screenshot leak and a future reader would otherwise trust an inaccurate claim.
- **Status**: OPEN (record-only, no action).

### DSC-5 — Security notes describe storage that no longer exists
- **Design**: `proposal.md` §Security notes — *"Uploaded files stored on local filesystem under a
  configurable `UPLOAD_DIR`. No path traversal risk as filenames are UUIDs."*
- **Code**: `f5f212b0` (skip-file-storage) deleted the entire `storage/` service tree and
  `UPLOAD_DIR` from config. Nothing is written to disk.
- **Adjudication**: stale design text, discovered incidentally while amending for DSC-3.
- **Caveat worth keeping**: that commit's privacy claim ("discard bytes") is only partly
  delivered — the extracted `raw_ocr_text` is still persisted to the DB, and until 2026-07-26 the
  full statement text was also written to container logs at INFO (finding #3).
- **Status**: CLOSED — design amended to match code, with the caveat recorded.

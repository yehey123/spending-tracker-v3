"""Email statement importer — Gmail → verify → unlock → flatten → POST /statements/upload.

Runs on the host (not in the backend container). Per message:
  1. Sender check: From address must exactly match a configured sender, and Gmail's
     Authentication-Results must show dkim=pass for that sender's domain (anti-spoofing).
  2. Attachment check + unlock + flatten, all inside a mandatory Docker sandbox
     (sandbox/: no network, read-only root, no capabilities, 512 MB, 120 s). Only
     PDF/PNG/JPEG by magic bytes, <= 20 MB. Every page is re-rendered to pixels and rebuilt
     as a new image-only PDF: no JavaScript, forms, links, or embedded files survive. The
     host never parses the original bytes and never writes them to disk.
  4. Upload the clean PDF to the app; the backend's OCR fallback reads image-only PDFs.
Processed message IDs go to <out>/.seen only after every attachment uploads, so a failed
run retries next time.

Config (all gitignored):
  secrets/email_senders.toml   sender list + password templates (see senders.example.toml)
  secrets/gmail_credentials.json, secrets/gmail_token.json   Gmail OAuth (read-only scope)
  .env   SPEND_EMAIL, SPEND_PASSWORD, and every placeholder the password templates use

Usage:
    python scripts/email_import/fetch.py [--dry-run] [--workers 10]

Exit codes:
    0  run finished (per-message failures are logged and retried next run)
    1  config missing or login failed
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import re
import subprocess
import sys
import threading
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SANDBOX = Path(__file__).resolve().parent / "sandbox"
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SANDBOX_FLAGS = ["--rm", "-i", "--network", "none", "--read-only", "--cap-drop", "ALL",
                 "--security-opt", "no-new-privileges", "--memory", "512m", "--memory-swap", "512m",
                 "--pids-limit", "64", "--cpus", "1"]
SANDBOX_TIMEOUT = 120  # seconds; a hang is treated as hostile


class Rejected(Exception):
    """Message or attachment failed a safety check; it is skipped and logged."""


def sandbox_image() -> str:
    """Build the flatten sandbox if missing. Tag = content hash, so edits force a rebuild."""
    digest = hashlib.sha256(b"".join((SANDBOX / f).read_bytes() for f in ("Dockerfile", "flatten.py")))
    tag = f"email-import-sandbox:{digest.hexdigest()[:12]}"
    if subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode != 0:
        subprocess.run(["docker", "build", "-q", "-t", tag, str(SANDBOX)], check=True, capture_output=True)
    return tag


def flatten(image: str, data: bytes, password: str | None) -> bytes:
    """Unlock + flatten inside the no-network, read-only container. Never parses on the host."""
    try:
        r = subprocess.run(["docker", "run", *SANDBOX_FLAGS, image],
                           input=(password or "").encode() + b"\n" + data,
                           capture_output=True, timeout=SANDBOX_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise Rejected(f"sandbox exceeded {SANDBOX_TIMEOUT}s") from None
    if r.returncode != 0:
        raise Rejected(f"sandbox exit {r.returncode}: {r.stderr.decode(errors='replace').strip()[-200:]}")
    if not r.stdout.startswith(b"%PDF-"):
        raise Rejected("sandbox output is not a PDF")
    return r.stdout


def load_env(path: Path) -> None:
    """Minimal .env reader: KEY=VALUE lines; real environment wins."""
    if path.exists():
        for line in path.read_text().splitlines():
            k, sep, v = line.partition("=")
            if sep and not k.lstrip().startswith("#"):
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def from_address(header: str) -> str:
    m = re.search(r"<([^>]+)>", header)
    return (m.group(1) if m else header).strip().lower()


def dkim_ok(auth_results: str, address: str) -> bool:
    """True if a dkim=pass signature's domain equals or is a parent of the sender domain."""
    domain = address.rsplit("@", 1)[-1]
    for d in re.findall(r"dkim=pass[^;]*?header\.(?:i=[^@\s;]*@|d=)([\w.-]+)", auth_results, re.I):
        d = d.lower()
        if domain == d or domain.endswith("." + d):
            return True
    return False


def password_for(sender: dict) -> str | None:
    """Fill the template's {PLACEHOLDERS} from env. Missing placeholder → Rejected."""
    tpl = sender.get("password")
    if not tpl:
        return None
    try:
        return tpl.format_map(os.environ)
    except KeyError as e:
        raise Rejected(f"password placeholder {e} not set in env") from None


def walk(part: dict):
    yield part
    for child in part.get("parts", []):
        yield from walk(child)


def attachment_parts(payload: dict) -> list[dict]:
    return [p for p in walk(payload)
            if p.get("filename") and re.match(r"application/pdf|image/(png|jpe?g)", p.get("mimeType", ""))]


def load_creds(cred_path: Path, token_path: Path):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    c = Credentials.from_authorized_user_file(str(token_path), SCOPES) if token_path.exists() else None
    if c and c.expired and c.refresh_token:
        c.refresh(Request())
    if not c or not c.valid:
        c = InstalledAppFlow.from_client_secrets_file(str(cred_path), SCOPES).run_local_server(port=0)
    token_path.write_text(c.to_json())
    token_path.chmod(0o600)
    return c


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="save clean PDFs locally, do not upload")
    parser.add_argument("--workers", type=int, default=10, help="parallel Gmail fetches (quota caps ~50 msg/s)")
    args = parser.parse_args()

    load_env(REPO / ".env")
    secrets = REPO / "secrets"
    cfg_path = secrets / "email_senders.toml"
    if not cfg_path.exists():
        print(f"missing {cfg_path} (copy scripts/email_import/senders.example.toml)", file=sys.stderr)
        return 1
    senders = {s["address"].lower(): s for s in tomllib.loads(cfg_path.read_text())["sender"]}
    out = Path(os.environ.get("EMAIL_IMPORT_DIR", REPO / "uploads" / "email"))
    api = os.environ.get("SPEND_API_URL", "http://localhost")

    try:  # mandatory: no sandbox, no run — attachments are never parsed on the host
        image = sandbox_image()
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"Docker sandbox unavailable ({e}); start Docker Desktop and rerun", file=sys.stderr)
        return 1

    import httpx
    from googleapiclient.discovery import build

    jwt = None
    if not args.dry_run:
        r = httpx.post(f"{api}/auth/login", json={
            "email": os.environ.get("SPEND_EMAIL", ""), "password": os.environ.get("SPEND_PASSWORD", ""),
            "device_name": "email-import"})
        if r.status_code != 200:
            print(f"login failed: HTTP {r.status_code}", file=sys.stderr)
            return 1
        jwt = r.json()["access_token"]  # 15-min lifetime; one run finishes well inside it

    creds = load_creds(secrets / "gmail_credentials.json", secrets / "gmail_token.json")
    local = threading.local()

    def svc():  # httplib2 is not thread-safe: one client per thread
        if not hasattr(local, "s"):
            local.s = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return local.s.users()

    def process(mid: str) -> str | None:
        try:
            m = svc().messages().get(userId="me", id=mid).execute(num_retries=5)
            h = {x["name"].lower(): x["value"] for x in m["payload"]["headers"]}
            addr = from_address(h.get("from", ""))
            sender = senders.get(addr)
            if sender is None:
                raise Rejected(f"From {addr!r} is not an exact configured sender")
            if not dkim_ok(h.get("authentication-results", ""), addr):
                raise Rejected(f"no dkim=pass for {addr}'s domain (possible spoof)")
            pw = password_for(sender)
            date = time.strftime("%Y-%m-%d", time.gmtime(int(m["internalDate"]) / 1000))
            for i, p in enumerate(attachment_parts(m["payload"])):
                body = p.get("body", {})
                data = body.get("data") or svc().messages().attachments().get(
                    userId="me", messageId=mid, id=body["attachmentId"]).execute(num_retries=5)["data"]
                clean = flatten(image, base64.urlsafe_b64decode(data), pw)
                name = f"{date}_{addr}_{mid[:8]}_{i}.pdf"
                (out / name).write_bytes(clean)
                if jwt:
                    r = httpx.post(f"{api}/api/statements/upload", headers={"Authorization": f"Bearer {jwt}"},
                                   files={"file": (name, clean, "application/pdf")},
                                   data={"statement_kind": sender.get("kind", "bank_account"),
                                         **({"type": "receipt"} if sender.get("kind") == "receipt" else {})},
                                   timeout=300)
                    if r.status_code != 200:
                        print(f"{mid}: upload HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
                        return None  # retry next run
            return mid
        except Rejected as e:
            print(f"{mid}: rejected: {e}", file=sys.stderr)
            return mid  # a rejected message stays rejected; do not retry forever
        except Exception as e:  # network/parse error: log and retry next run
            print(f"{mid}: error: {type(e).__name__}: {e}", file=sys.stderr)
            return None

    out.mkdir(parents=True, exist_ok=True)
    seen_path = out / ".seen"
    seen = set(seen_path.read_text().split()) if seen_path.exists() else set()
    query, ids, token = f"from:({' OR '.join(senders)}) has:attachment", [], None
    while True:
        r = svc().messages().list(userId="me", q=query, pageToken=token, maxResults=500).execute(num_retries=5)
        ids += [x["id"] for x in r.get("messages", [])]
        if not (token := r.get("nextPageToken")):
            break
    todo = [i for i in ids if i not in seen]
    print(f"{len(todo)} new of {len(ids)} matching messages")
    # ponytail: uploads run in the same pool; if backend OCR becomes the bottleneck, cap upload concurrency separately
    with ThreadPoolExecutor(args.workers) as pool, seen_path.open("a") as f:
        for mid in pool.map(process, todo):
            if mid:
                f.write(mid + "\n")
                f.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Sandboxed flatten worker — runs ONLY inside the email-import-sandbox container.

Protocol: stdin = password line (UTF-8, may be empty) + "\\n" + raw attachment bytes.
          stdout = clean image-only PDF.
Exit codes: 0 ok · 3 rejected (reason on stderr) · anything else = crash (treated as rejected).

The container runs with no network, a read-only root, no capabilities, and an
unprivileged user, so a parser exploit here cannot reach the host, secrets, or network.
"""

from __future__ import annotations

import sys

MAGIC = (b"%PDF-", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")
MAX_SIZE = 20 * 1024 * 1024  # matches backend _MAX_SIZE
MAX_PAGES = 50
DPI = 200  # backend OCR rasterizes at 150; render above that so OCR quality holds


class Rejected(Exception):
    """Attachment failed a safety check."""


def flatten(data: bytes, password: str | None) -> bytes:
    """Validate, unlock, and rebuild as an image-only PDF."""
    import pymupdf as fitz  # not `import fitz`: 1.28 prints a deprecation warning to stdout

    if len(data) > MAX_SIZE:
        raise Rejected("attachment exceeds 20 MB")
    if not data.startswith(MAGIC):
        raise Rejected("not a PDF/PNG/JPEG by magic bytes")
    src = fitz.open(stream=data)
    if src.needs_pass and not (password and src.authenticate(password)):
        raise Rejected("PDF is encrypted and the password template did not unlock it")
    if src.page_count > MAX_PAGES:
        raise Rejected(f"more than {MAX_PAGES} pages")
    out = fitz.open()
    for page in src:
        pix = page.get_pixmap(dpi=DPI)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=pix.tobytes("png"))
    return out.tobytes(garbage=4, deflate=True)


def main() -> int:
    raw = sys.stdin.buffer.read()
    pw_line, _, data = raw.partition(b"\n")
    try:
        sys.stdout.buffer.write(flatten(data, pw_line.decode() or None))
    except Rejected as e:
        print(e, file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

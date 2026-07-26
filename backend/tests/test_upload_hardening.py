"""Tests for statement upload hardening (POST /statements/upload).

Spec provenance (blueprint Step 3 / security findings #6, #7):
  C1/C2. A declared MIME that disagrees with the file's magic bytes is rejected.
         Previously the client-supplied Content-Type was trusted blindly, so a
         crafted file could reach the PIL / pdfplumber parsers.
  C3.    A body over the 20 MB cap is rejected. The cap is enforced during a
         chunked read, so an oversized POST is aborted mid-stream rather than
         being fully buffered first.
  C4.    A file whose magic bytes match its declared type passes validation and
         reaches the pipeline.
"""

from unittest.mock import AsyncMock, patch

import pytest

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PDF_MAGIC = b"%PDF-"

_MISMATCH_DETAIL = "File content does not match its declared type."
_OVERSIZE_DETAIL = "File exceeds 20 MB limit."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "declared_type, filename, body",
    [
        ("image/png", "fake.png", _JPEG_MAGIC + b"\x00" * 64),
        ("image/jpeg", "fake.jpg", _PNG_MAGIC + b"\x00" * 64),
        ("application/pdf", "fake.pdf", _PNG_MAGIC + b"\x00" * 64),
        ("image/png", "fake.png", b"<?php system($_GET[0]); ?>"),
    ],
)
async def test_declared_type_must_match_magic_bytes(
    client, declared_type, filename, body
) -> None:
    """C1/C2 — the Content-Type header alone is no longer sufficient."""
    res = await client.post(
        "/statements/upload",
        files={"file": (filename, body, declared_type)},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == _MISMATCH_DETAIL


@pytest.mark.asyncio
async def test_oversize_upload_rejected(client) -> None:
    """C3 — a body beyond the 20 MB cap is refused."""
    oversize = _PNG_MAGIC + b"\x00" * (21 * 1024 * 1024)
    res = await client.post(
        "/statements/upload",
        files={"file": ("big.png", oversize, "image/png")},
    )
    assert res.status_code == 400
    assert res.json()["detail"] == _OVERSIZE_DETAIL


@pytest.mark.asyncio
async def test_matching_magic_bytes_reach_pipeline(client) -> None:
    """C4 — a well-formed upload is not rejected by either guard."""
    valid_png = _PNG_MAGIC + b"\x00" * 128

    with patch(
        "src.domain.services.statement_pipeline.statement_pipeline.run",
        new=AsyncMock(return_value=([], False)),
    ) as mock_run:
        res = await client.post(
            "/statements/upload",
            files={"file": ("real.png", valid_png, "image/png")},
        )

    assert res.status_code not in (400,), f"valid PNG rejected: {res.text}"
    mock_run.assert_called_once()

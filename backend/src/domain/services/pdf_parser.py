"""PDF text extraction with pdfplumber, falling back to OCR for image-based PDFs.

Stage 3 of the OCR pipeline (ocr-pipeline.md §Stage 3):
    pdfplumber → text/tables; falls back to per-page rasterize+OCR if empty.
"""

from __future__ import annotations

import io
import re

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None  # type: ignore[assignment]

OCR_RENDER_DPI = 300
_WATERMARK_LINE_RE = re.compile(r"^[A-Za-z]$")


def _clean_cell(cell: object) -> str:
    """Join a table cell's lines, dropping lone letters a diagonal watermark injects."""
    lines = str(cell or "").splitlines()
    return " ".join(ln.strip() for ln in lines if ln.strip() and not _WATERMARK_LINE_RE.match(ln.strip()))


async def extract_pdf_text(
    content: bytes, ocr_provider: object, categories: list[dict] | None = None
) -> str:
    """Extract text from a PDF, falling back to OCR if the PDF is image-based.

    Args:
        content: Raw PDF file bytes.
        ocr_provider: Duck-typed object with ``async extract_text(image) -> str``.
        categories: Optional list of {id, name} dicts; passed to AI providers so they
            can embed category names in the output in a single call.

    Returns:
        The full extracted text, page texts joined by newline.
    """
    if pdfplumber is None:  # pragma: no cover
        raise RuntimeError(
            "pdfplumber is required for PDF extraction. Install it with: pip install pdfplumber"
        )

    page_texts: list[str] = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                # Render each table as pipe-delimited rows; empty cells are kept so
                # debit/credit column positions survive
                table_rows: list[str] = []
                for table in tables:
                    for row in table:
                        cells = [_clean_cell(c) for c in row]
                        if any(cells):
                            table_rows.append(" | ".join(cells))
                page_texts.append("\n".join(table_rows))
            else:
                page_texts.append(page.extract_text() or "")

        full_text = "\n".join(page_texts)

        if not full_text.strip():
            # Image-based PDF — rasterize each page at its native scan DPI
            # (capped at OCR_RENDER_DPI), then OCR
            ocr_texts: list[str] = []
            for page in pdf.pages:
                dpis = [72 * i["srcsize"][0] / i["width"] for i in page.images
                        if i.get("srcsize") and i.get("width")]
                dpi = min(OCR_RENDER_DPI, max(dpis)) if dpis else OCR_RENDER_DPI
                pil_img = page.to_image(resolution=dpi).original
                text = await ocr_provider.extract_with_categories(pil_img, categories or [])  # type: ignore[attr-defined]
                ocr_texts.append(text)
            full_text = "\n".join(ocr_texts)

    return full_text

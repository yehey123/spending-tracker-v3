"""PDF text extraction with pdfplumber, falling back to OCR for image-based PDFs.

Stage 3 of the OCR pipeline (ocr-pipeline.md §Stage 3):
    pdfplumber → text/tables; falls back to per-page rasterize+OCR if empty.
"""

from __future__ import annotations

import io

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None  # type: ignore[assignment]

from src.domain.services.preprocessor import preprocess


async def extract_pdf_text(content: bytes, ocr_provider: object) -> str:
    """Extract text from a PDF, falling back to OCR if the PDF is image-based.

    Args:
        content: Raw PDF file bytes.
        ocr_provider: Duck-typed object with ``async extract_text(image) -> str``.

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
                # Render each table as pipe-delimited rows
                table_rows: list[str] = []
                for table in tables:
                    for row in table:
                        row_text = " | ".join(str(c) for c in row if c)
                        if row_text:
                            table_rows.append(row_text)
                page_texts.append("\n".join(table_rows))
            else:
                page_texts.append(page.extract_text() or "")

        full_text = "\n".join(page_texts)

        if not full_text.strip():
            # Image-based PDF — rasterize each page, preprocess, then OCR
            ocr_texts: list[str] = []
            for page in pdf.pages:
                pil_img = page.to_image(resolution=150).original
                preprocessed = preprocess(pil_img)
                text = await ocr_provider.extract_text(preprocessed)  # type: ignore[attr-defined]
                ocr_texts.append(text)
            full_text = "\n".join(ocr_texts)

    return full_text

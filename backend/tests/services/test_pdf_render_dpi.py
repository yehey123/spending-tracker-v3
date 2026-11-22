"""OCR rasterize resolution — image-only PDF pages must render at >= 300 DPI."""

import asyncio
from pathlib import Path
from unittest.mock import patch

from src.domain.services import pdf_parser

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "ocr_synthetic" / "bank_a_scan.pdf"


class _RecordingProvider:
    def __init__(self) -> None:
        self.widths: list[int] = []

    async def extract_with_categories(self, image, categories):
        self.widths.append(image.size[0])
        return ""


def test_image_only_pdf_rasterized_at_ocr_render_dpi():
    # preprocess() upscales small renders, which would mask the render DPI; stub it out
    # so the recorded width reflects only the rasterize resolution.
    provider = _RecordingProvider()
    with patch.object(pdf_parser, "preprocess", lambda img: img):
        asyncio.run(pdf_parser.extract_pdf_text(FIXTURE.read_bytes(), provider, []))

    assert provider.widths, "OCR provider was never called for the image-only PDF"
    assert min(provider.widths) >= 2400, (
        f"page rendered at {min(provider.widths)} px wide; expected >= 2400 (300 DPI letter)"
    )

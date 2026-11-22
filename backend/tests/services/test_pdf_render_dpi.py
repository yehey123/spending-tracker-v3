"""OCR rasterize resolution — image-only PDF pages must render at >= 300 DPI."""

import asyncio
import io
from pathlib import Path

from PIL import Image

from src.domain.services import pdf_parser

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "ocr_synthetic" / "bank_a_scan.pdf"


class _RecordingProvider:
    def __init__(self) -> None:
        self.widths: list[int] = []

    async def extract_with_categories(self, image, categories):
        self.widths.append(image.size[0])
        return ""


def test_image_only_pdf_rasterized_at_ocr_render_dpi():
    provider = _RecordingProvider()
    asyncio.run(pdf_parser.extract_pdf_text(FIXTURE.read_bytes(), provider, []))

    assert provider.widths, "OCR provider was never called for the image-only PDF"
    assert min(provider.widths) >= 2400, (
        f"page rendered at {min(provider.widths)} px wide; expected >= 2400 (300 DPI letter)"
    )


def test_native_resolution_pdf_not_oversampled():
    # Page pts == image pixels (72 dpi scan): a fixed 300 DPI render would be 4.17x.
    buf = io.BytesIO()
    Image.new("RGB", (600, 800), "white").save(buf, format="PDF", resolution=72)
    provider = _RecordingProvider()
    asyncio.run(pdf_parser.extract_pdf_text(buf.getvalue(), provider, []))

    assert provider.widths, "OCR provider was never called for the image-only PDF"
    assert max(provider.widths) <= 600, f"rendered {max(provider.widths)} px wide from a 600 px source"

import asyncio

import pytesseract
from PIL import Image

from .base import OCRProvider


class TesseractProvider(OCRProvider):
    async def extract_text(self, image: Image.Image) -> str:
        # Run in executor so the blocking Tesseract call doesn't stall the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: pytesseract.image_to_string(image, config="--psm 6 --oem 1")
        )

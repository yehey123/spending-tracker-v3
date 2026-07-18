import pytesseract
from PIL import Image

from .base import OCRProvider


class TesseractProvider(OCRProvider):
    async def extract_text(self, image: Image.Image) -> str:
        # PSM 6 = uniform block of text; OEM 1 = LSTM only (more accurate than legacy)
        return pytesseract.image_to_string(image, config="--psm 6 --oem 1")

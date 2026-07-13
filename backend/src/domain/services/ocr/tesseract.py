import pytesseract
from PIL import Image

from .base import OCRProvider


class TesseractProvider(OCRProvider):
    async def extract_text(self, image: Image.Image) -> str:
        # PSM 6 = assume single uniform block of text (good for statement layouts)
        return pytesseract.image_to_string(image, config="--psm 6")

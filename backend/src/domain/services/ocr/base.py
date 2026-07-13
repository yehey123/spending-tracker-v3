from abc import ABC, abstractmethod

from PIL import Image


class OCRProvider(ABC):
    @abstractmethod
    async def extract_text(self, image: Image.Image) -> str:
        """Extract raw text from a preprocessed image."""
        ...

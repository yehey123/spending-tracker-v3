from abc import ABC, abstractmethod

from PIL import Image


class AIPackagesMissing(RuntimeError):
    """Raised when an AI provider is used but the optional SDKs are not installed."""


class OCRProvider(ABC):
    supports_categories: bool = False

    @abstractmethod
    async def extract_text(self, image: Image.Image) -> str:
        """Extract raw text from a preprocessed image."""
        ...

    async def extract_with_categories(self, image: Image.Image, categories: list[dict]) -> str:
        """Extract text and optionally embed category names in output.

        AI providers override this; non-AI providers fall back to extract_text.
        """
        return await self.extract_text(image)

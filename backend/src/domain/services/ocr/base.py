from abc import ABC, abstractmethod

from PIL import Image

_BASE_PROMPT = (
    "Extract EVERY transaction from this bank or credit card statement image. "
    "Do not stop early — list every single visible row from top to bottom without skipping any. "
    "Return one transaction per line in this exact format:\n"
    "DATE | DESCRIPTION | AMOUNT | DEBIT or CREDIT\n\n"
    "Use MM/DD/YYYY for dates. Amounts are numbers only, no currency symbols, no commas. "
    "If an amount has a trailing minus sign (e.g. 22000.00-), mark it as CREDIT. "
    "Output only transaction lines. No headers, no totals, no commentary. "
    "Continue until the very last visible transaction has been listed."
)


def _build_prompt(categories: list[dict] | None = None) -> str:
    if not categories:
        return _BASE_PROMPT
    names = ", ".join(f'"{c["name"]}"' for c in categories)
    return (
        _BASE_PROMPT
        + f"\n\nAlso assign each transaction a category. Available categories: {names}.\n"
        "Add a 5th pipe-delimited column with the exact category name, or leave it empty if none fits:\n"
        "DATE | DESCRIPTION | AMOUNT | DEBIT or CREDIT | CATEGORY"
    )


class OCRProvider(ABC):
    supports_categories: bool = False

    @abstractmethod
    async def extract_text(self, image: Image.Image) -> str:
        """Extract raw text from a preprocessed image."""
        ...

    async def extract_with_categories(
        self, image: Image.Image, categories: list[dict]
    ) -> str:
        """Extract text and optionally embed category names in output.

        AI providers override this; non-AI providers fall back to extract_text.
        """
        return await self.extract_text(image)

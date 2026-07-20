import base64
import io

from openai import OpenAI
from PIL import Image

from .base import OCRProvider

_PROMPT = (
    "Extract EVERY transaction from this bank or credit card statement image. "
    "Do not stop early — list every single visible row from top to bottom without skipping any. "
    "Return one transaction per line in this exact format:\n"
    "DATE | DESCRIPTION | AMOUNT | DEBIT or CREDIT\n\n"
    "Use MM/DD/YYYY for dates. Amounts are numbers only, no currency symbols, no commas. "
    "If an amount has a trailing minus sign (e.g. 22000.00-), mark it as CREDIT. "
    "Output only transaction lines. No headers, no totals, no commentary. "
    "Continue until the very last visible transaction has been listed."
)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class GeminiVisionProvider(OCRProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", max_tokens: int = 8192):
        self.client = OpenAI(api_key=api_key, base_url=_GEMINI_BASE_URL)
        self.model = model
        self.max_tokens = max_tokens

    async def extract_text(self, image: Image.Image) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode()

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded}"},
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )

        return response.choices[0].message.content

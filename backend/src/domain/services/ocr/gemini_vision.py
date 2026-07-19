import base64
import io

from openai import OpenAI
from PIL import Image

from .base import OCRProvider

_PROMPT = (
    "Extract every transaction from this bank or credit card statement image. "
    "Return one transaction per line in this exact format:\n"
    "DATE | DESCRIPTION | AMOUNT | DEBIT or CREDIT\n\n"
    "Use MM/DD/YYYY for dates. Amounts are numbers only, no currency symbols. "
    "Output only the transaction lines, no headers or commentary."
)

_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class GeminiVisionProvider(OCRProvider):
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.client = OpenAI(api_key=api_key, base_url=_GEMINI_BASE_URL)
        self.model = model

    async def extract_text(self, image: Image.Image) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode()

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=4096,
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

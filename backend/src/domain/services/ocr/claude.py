import base64
import io

import anthropic
from PIL import Image

from .base import OCRProvider

_PROMPT = (
    "Extract every transaction from this bank or credit card statement image. "
    "Return one transaction per line in this exact format:\n"
    "DATE | DESCRIPTION | AMOUNT | DEBIT or CREDIT\n\n"
    "Use MM/DD/YYYY for dates. Amounts are numbers only, no currency symbols. "
    "Output only the transaction lines, no headers or commentary."
)


class ClaudeVisionProvider(OCRProvider):
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    async def extract_text(self, image: Image.Image) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode()

        message = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": encoded,
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )

        return message.content[0].text

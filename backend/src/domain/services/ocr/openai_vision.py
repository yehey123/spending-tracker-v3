import base64
import io

from openai import OpenAI
from PIL import Image

from .base import OCRProvider, _build_prompt, SYSTEM_PROMPT


class OpenAIVisionProvider(OCRProvider):
    supports_categories = True

    def __init__(self, api_key: str, model: str = "gpt-4o", max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.client = OpenAI(api_key=api_key)

    async def _call(self, image: Image.Image, prompt: str) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode()

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            tool_choice="none",                  # RULE-AI-EXEC-1
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,    # system prompt policy
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                },
            ],
        )
        return response.choices[0].message.content

    async def extract_text(self, image: Image.Image) -> str:
        return await self._call(image, _build_prompt())

    async def extract_with_categories(self, image: Image.Image, categories: list[dict]) -> str:
        return await self._call(image, _build_prompt(categories))

import base64
import io

import anthropic
from PIL import Image

from .base import OCRProvider, _build_prompt, SYSTEM_PROMPT


class ClaudeVisionProvider(OCRProvider):
    supports_categories = True

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6", max_tokens: int = 4096):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=api_key)

    async def _call(self, image: Image.Image, prompt: str) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode()

        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,                # RULE-AI-EXEC-1 + system prompt policy
            tools=[],                            # RULE-AI-EXEC-1: disable tool registration
            tool_choice={"type": "none"},        # RULE-AI-EXEC-1: explicitly forbid tool calls
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
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return message.content[0].text

    async def extract_text(self, image: Image.Image) -> str:
        return await self._call(image, _build_prompt())

    async def extract_with_categories(self, image: Image.Image, categories: list[dict]) -> str:
        return await self._call(image, _build_prompt(categories))

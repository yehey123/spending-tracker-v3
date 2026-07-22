import base64
import io
import logging

from PIL import Image

from .base import OCRProvider, _build_prompt

_log = logging.getLogger(__name__)


class VertexVisionProvider(OCRProvider):
    supports_categories = True

    def __init__(self, project_id: str, location: str = "us-central1",
                 model: str = "google/gemini-2.5-flash", max_tokens: int = 8192):
        self.project_id = project_id
        self.location = location
        self.model = model if "/" in model else f"google/{model}"
        self.max_tokens = max_tokens

    async def _call(self, image: Image.Image, prompt: str) -> str:
        import google.auth
        import google.auth.transport.requests
        from openai import OpenAI

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        creds.refresh(google.auth.transport.requests.Request())

        endpoint = (
            f"https://{self.location}-aiplatform.googleapis.com/v1beta1/projects/"
            f"{self.project_id}/locations/{self.location}/endpoints/openapi/"
        )
        client = OpenAI(api_key=creds.token, base_url=endpoint)

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode()

        _log.info("Vertex OCR: model=%s image=%dx%d", self.model, image.width, image.height)

        response = client.chat.completions.create(
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
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        choice = response.choices[0]
        _log.info("Vertex OCR: finish_reason=%s output_tokens=%s",
                  choice.finish_reason,
                  getattr(response.usage, "completion_tokens", "?"))
        return choice.message.content

    async def extract_text(self, image: Image.Image) -> str:
        return await self._call(image, _build_prompt())

    async def extract_with_categories(self, image: Image.Image, categories: list[dict]) -> str:
        return await self._call(image, _build_prompt(categories))

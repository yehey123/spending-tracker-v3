import base64
import io

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


class VertexVisionProvider(OCRProvider):
    def __init__(self, project_id: str, location: str = "us-central1",
                 model: str = "google/gemini-2.5-flash", max_tokens: int = 8192):
        self.project_id = project_id
        self.location = location
        # Vertex OpenAI-compat endpoint requires "<publisher>/<model>" format
        self.model = model if "/" in model else f"google/{model}"
        self.max_tokens = max_tokens

    async def extract_text(self, image: Image.Image) -> str:
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

        import logging
        _log = logging.getLogger(__name__)
        _log.info("Vertex OCR: model=%s image=%dx%d encoded_bytes=%d",
                  self.model, image.width, image.height, len(encoded))

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
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )

        choice = response.choices[0]
        _log.info("Vertex OCR: finish_reason=%s output_tokens=%s",
                  choice.finish_reason,
                  getattr(response.usage, 'completion_tokens', '?'))
        return choice.message.content

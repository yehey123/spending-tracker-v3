import base64
import io

from PIL import Image

from .base import OCRProvider

_PROMPT = (
    "Extract every transaction from this bank or credit card statement image. "
    "Return one transaction per line in this exact format:\n"
    "DATE | DESCRIPTION | AMOUNT | DEBIT or CREDIT\n\n"
    "Use MM/DD/YYYY for dates. Amounts are numbers only, no currency symbols. "
    "Output only the transaction lines, no headers or commentary."
)


class VertexVisionProvider(OCRProvider):
    def __init__(self, project_id: str, location: str = "us-central1",
                 model: str = "google/gemini-2.5-flash"):
        self.project_id = project_id
        self.location = location
        self.model = model

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

        response = client.chat.completions.create(
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

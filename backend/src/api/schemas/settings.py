from typing import Literal

from pydantic import BaseModel


class SettingsOut(BaseModel):
    ocr_provider: str
    anthropic_api_key_set: bool
    openai_api_key_set: bool


class SettingsPut(BaseModel):
    ocr_provider: Literal["tesseract", "claude", "openai"]
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

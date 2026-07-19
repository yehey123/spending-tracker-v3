from typing import Literal

from pydantic import BaseModel, Field


class SettingsOut(BaseModel):
    ocr_provider: str
    anthropic_api_key_set: bool
    openai_api_key_set: bool
    home_currency: str | None = None
    review_before_commit: bool = True
    ai_category_confidence_auto: float = 0.85
    ai_category_confidence_suggest: float = 0.50
    ai_provider: str = "anthropic"
    ai_model: str | None = None
    ai_api_url: str | None = None
    gemini_api_key_set: bool = False
    google_project_id: str | None = None
    google_location: str | None = None


class SettingsPut(BaseModel):
    ocr_provider: Literal["tesseract", "claude", "openai"] | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    home_currency: str | None = None
    review_before_commit: bool | None = None
    ai_category_confidence_auto: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_category_confidence_suggest: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_provider: Literal["anthropic", "openai", "gemini", "vertex", "local"] | None = None
    ai_model: str | None = None
    ai_api_url: str | None = None
    gemini_api_key: str | None = None
    google_project_id: str | None = None
    google_location: str | None = None

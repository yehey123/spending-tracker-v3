from pydantic import BaseModel, Field


class ConfigFieldOut(BaseModel):
    name: str
    label: str
    secret: bool = False
    required: bool = False
    set: bool = False


class ProviderOut(BaseModel):
    key: str
    label: str
    config_fields: list[ConfigFieldOut] = []


class SettingsOut(BaseModel):
    ocr_provider: str
    available_providers: list[ProviderOut] = []
    provider_installed: bool = True
    anthropic_api_key_set: bool
    openai_api_key_set: bool
    home_currency: str | None = None
    review_before_commit: bool = True
    ai_category_confidence_auto: float = 0.85
    ai_category_confidence_suggest: float = 0.50
    ai_model: str | None = None
    gemini_api_key_set: bool = False
    google_project_id: str | None = None
    google_location: str | None = None
    max_output_tokens: int | None = None
    dev_mode: bool = False
    dev_mode_available: bool = True


class SettingsPut(BaseModel):
    ocr_provider: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    home_currency: str | None = None
    review_before_commit: bool | None = None
    ai_category_confidence_auto: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_category_confidence_suggest: float | None = Field(default=None, ge=0.0, le=1.0)
    ai_model: str | None = None
    gemini_api_key: str | None = None
    google_project_id: str | None = None
    google_location: str | None = None
    max_output_tokens: int | None = Field(default=None, ge=256)
    dev_mode: bool | None = None

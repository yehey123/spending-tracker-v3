from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/spending_tracker"

    upload_dir: str = "/tmp/spending-tracker-uploads"

    # OCR defaults — overridable from the DB settings table at runtime
    ocr_provider: str = "tesseract"  # tesseract | claude | openai
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


settings = Settings()

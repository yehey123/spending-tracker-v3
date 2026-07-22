from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/spending_tracker"

    upload_dir: str = "/tmp/spending-tracker-uploads"

    # Storage backends — comma-separated: "local", "s3", "gcs", "local,s3", etc.
    storage_backends: str = "local"

    # AWS / S3
    aws_s3_bucket: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str | None = None
    aws_endpoint_url: str | None = None  # for R2/MinIO/B2

    # GCS
    gcs_bucket: str | None = None
    gcs_project_id: str | None = None
    google_application_credentials: str | None = None

    # Exchange rate SQLite cache
    rates_db_path: str = "/data/rates/exchange_rates.db"

    # OCR defaults — overridable from the DB settings table at runtime
    ocr_provider: str = "tesseract"  # tesseract | claude | openai
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None

    # Model selection — applies to whichever OCR/AI provider is active
    ai_model: str | None = None
    gemini_api_key: str | None = None
    google_project_id: str | None = None   # Vertex AI project
    google_location: str = "us-central1"  # Vertex AI region

    # Account fingerprinting — must be ≥ 32 chars when account numbers are stored
    app_secret: str = ""

    # Environment — set APP_ENV=development to enable dev-only features (e.g. dev_mode)
    app_env: str = "production"


settings = Settings()

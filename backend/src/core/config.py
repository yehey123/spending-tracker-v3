from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/spending_tracker"

    # Runtime connection URL used by the app (non-superuser role so RLS is enforced).
    # Falls back to database_url when not set (e.g. local dev without a separate app role).
    app_db_url: str | None = None

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

    # Shared-secret API auth — empty string disables auth (dev only)
    api_token: str = ""

    # Comma-separated list of allowed CORS origins; empty falls back to dev/Capacitor defaults
    cors_origins: str = ""

    # JWT / HMAC secret — used for signing admin approve/deny links (E11).
    # Must be ≥ 32 chars in production. Falls back to app_secret when empty.
    jwt_secret: str = ""

    # Gmail SMTP (E11 — invite gate)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""          # e.g. spendingtracker.noreply@gmail.com
    smtp_password: str = ""      # Gmail App Password (16-char, no spaces)

    # Public base URL used in email links (E11). Set in production env.
    app_base_url: str = "http://localhost:8000"

    # Google OAuth (E12)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    # Upstash Redis — for async OCR queue (set to empty string to disable)
    upstash_redis_url: str | None = None


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/avox_revenue_gaps"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    ALLOWED_ORIGINS: str = (
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o"
    LLM_MODEL_MINI: str = "gpt-4o-mini"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    PDF_OUTPUT_DIR: str = "storage/pdfs"

    GOOGLE_SHEETS_SPREADSHEET_ID: str = ""
    GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE: str = ""
    GOOGLE_SHEETS_WORKSHEET_TITLE: str = "AVOX Submissions"

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    CRAWL_REQUEST_DELAY_SEC: float = 0.4
    PAGE_LOAD_CONCURRENCY: int = 1

    PIPELINE_MAX_RETRIES: int = 4
    PIPELINE_RETRY_COUNTDOWN_SEC: int = 300

    # Проксі лише для SimilarWeb (worker). http://… або https://…; без схеми — http://
    SIMILARWEB_PROXY: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    BOT_TOKEN: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    DATABASE_URL: str
    NEMOTRON_API_KEY: str
    ENCRYPTION_KEY: str
    GITHUB_PAT: str
    GITHUB_OWNER: str
    GITHUB_REPO: str
    SENTRY_DSN: Optional[str] = None
    
    # Webhook config
    WEBHOOK_PATH: str = "/telegram/webhook"
    WEBHOOK_URL: Optional[str] = None
    
    # FastAPI options
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

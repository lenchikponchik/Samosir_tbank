"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings loaded from environment."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://zarabotok:change_me_in_production@localhost:5432/zarabotok_db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # ML Service
    ML_SERVICE_URL: str = "http://ml_service:8001"
    ML_SERVICE_TIMEOUT: float = 30.0

    # Anthropic Claude
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # App
    SECRET_KEY: str = "change_me_to_random_string"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()

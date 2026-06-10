"""
Application configuration via environment variables.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings loaded from environment variables / .env file."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/xeno"

    # Redis (Upstash)
    REDIS_URL: str = "redis://localhost:6379"

    # Channel Service
    CHANNEL_SERVICE_URL: str = "http://localhost:8001"

    # AI Providers
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Backend (self-URL for callbacks)
    BACKEND_URL: str = "http://localhost:8000"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    # App
    DEBUG: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()

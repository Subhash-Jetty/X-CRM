"""
Application configuration via environment variables.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings loaded from environment variables / .env file."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/xeno"

    # Channel Service
    CHANNEL_SERVICE_URL: str = "http://127.0.0.1:8001"

    # AI Providers
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Backend (self-URL for callbacks)
    BACKEND_URL: str = "http://127.0.0.1:8000"

    # Frontend
    FRONTEND_URL: str = "http://127.0.0.1:3000"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        import os
        # Automatically use Render's external URL if BACKEND_URL is default
        render_url = os.environ.get("RENDER_EXTERNAL_URL")
        if render_url and self.BACKEND_URL == "http://127.0.0.1:8000":
            self.BACKEND_URL = render_url

    # App
    DEBUG: bool = False

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()

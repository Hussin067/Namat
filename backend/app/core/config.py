"""Application settings, loaded from environment variables and backend/.env.

Real values live only in backend/.env (git-ignored) or in the host's
environment variables. backend/.env.example documents the expected keys.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory, so .env is found no matter which folder you run from.
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"

    # SecretStr hides the password if settings are ever printed or logged.
    # Read the real value with settings.database_url.get_secret_value().
    database_url: SecretStr

    frontend_url: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()

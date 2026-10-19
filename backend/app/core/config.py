"""Application settings, loaded from environment variables and backend/.env.

Real values live only in backend/.env (git-ignored) or in the host's
environment variables. backend/.env.example documents the expected keys.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

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

    # --- Authentication (JWT access tokens) ---
    # Random secret used to sign tokens. Generate it locally; never commit it.
    jwt_secret_key: SecretStr
    # Fixed on purpose: tokens signed with any other algorithm are rejected.
    jwt_algorithm: Literal["HS256"] = "HS256"
    # Short-lived tokens limit the damage if one is stolen.
    access_token_expire_minutes: int = Field(default=20, ge=5, le=60)

    @field_validator("jwt_secret_key")
    @classmethod
    def secret_must_be_strong(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret) < 32 or "CHANGE_ME" in secret:
            raise ValueError(
                "JWT_SECRET_KEY must be a random value of at least 32 characters "
                "(see backend/.env.example for how to generate one)"
            )
        return value

    @model_validator(mode="after")
    def secret_differs_from_db_password(self) -> "Settings":
        db_password = make_url(self.database_url.get_secret_value()).password
        if db_password and db_password == self.jwt_secret_key.get_secret_value():
            raise ValueError("JWT_SECRET_KEY must not reuse the database password")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

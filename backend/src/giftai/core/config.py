"""Application settings, read once from environment variables (or a local .env file).

Every setting the app needs is declared here with its type, so a missing or malformed
value fails fast at startup with a clear message instead of deep inside a request.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.TEXT

    # Kept secret so the password never appears in logs or reprs.
    database_url: SecretStr
    # Aiven's free plan allows 20 connections and has no pooler, so the pool stays small.
    database_pool_size: int = Field(default=5, ge=1, le=15)
    database_max_overflow: int = Field(default=2, ge=0, le=5)
    database_pool_timeout_seconds: float = Field(default=10.0, gt=0)

    # NoDecode lets the validator below accept a plain comma-separated string.
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("database_url")
    @classmethod
    def _require_postgres_url(cls, value: SecretStr) -> SecretStr:
        # Validate the shape without storing it as a non-secret type.
        PostgresDsn(value.get_secret_value())
        return value

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def sqlalchemy_database_url(self) -> str:
        """The database URL with SQLAlchemy's psycopg 3 driver (sync and async) selected.

        Hosts such as Aiven hand out plain ``postgres://`` URLs; this normalises them so
        the same value can be pasted into the environment unchanged.
        """
        url = self.database_url.get_secret_value()
        for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url.removeprefix(prefix)
        return url


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, loading them on first use."""
    return Settings()

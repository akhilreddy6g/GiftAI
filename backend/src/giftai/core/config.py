"""Application settings, read once from environment variables (or a local .env file).

Every setting is declared here with its type, so a missing or malformed value fails fast
at startup with a clear message instead of deep inside a request.

``DatabaseSettings`` and ``EmbeddingSettings`` hold only what migrations and the offline
catalog pipeline need, so they run without the web app's configuration. ``Settings`` adds
everything the API needs.
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, HttpUrl, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class LogFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Kept secret so the password never appears in logs or reprs.
    database_url: SecretStr
    # Aiven's free plan allows 20 connections and has no pooler, so the pool stays small.
    database_pool_size: int = Field(default=5, ge=1, le=15)
    database_max_overflow: int = Field(default=2, ge=0, le=5)
    database_pool_timeout_seconds: float = Field(default=10.0, gt=0)

    @field_validator("database_url")
    @classmethod
    def _require_postgres_url(cls, value: SecretStr) -> SecretStr:
        # Validate the shape without storing it as a non-secret type.
        PostgresDsn(value.get_secret_value())
        return value

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


class EmbeddingSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # The catalog and every search query must be embedded by this same model; changing it
    # means re-running the catalog pipeline.
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    # Where the model files are cached. The Docker image bakes them in, so production
    # never downloads at runtime; unset means fastembed's default cache folder.
    embedding_cache_dir: Path | None = None


class Settings(DatabaseSettings, EmbeddingSettings):
    environment: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_format: LogFormat = LogFormat.TEXT

    # NoDecode lets the validator below accept a plain comma-separated string.
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Supabase only signs users in; the API verifies its tokens with the project's public
    # signing keys, so no Supabase secret is needed here.
    supabase_url: HttpUrl
    supabase_jwt_audience: str = "authenticated"
    supabase_jwks_cache_seconds: int = Field(default=600, ge=60)

    # Abuse protection: per-user request budget and a cap on request body size.
    rate_limit_requests_per_minute: int = Field(default=60, ge=1)
    max_request_body_bytes: int = Field(default=64 * 1024, ge=1024)

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
    def supabase_auth_issuer(self) -> str:
        """The ``iss`` claim Supabase puts in the tokens it signs for this project."""
        return f"{str(self.supabase_url).rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        return f"{self.supabase_auth_issuer}/.well-known/jwks.json"


@lru_cache
def get_database_settings() -> DatabaseSettings:
    """Database settings alone, for migrations and scripts."""
    return DatabaseSettings()


@lru_cache
def get_embedding_settings() -> EmbeddingSettings:
    """Embedding settings alone, for the offline catalog pipeline."""
    return EmbeddingSettings()


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings, loading them on first use."""
    return Settings()

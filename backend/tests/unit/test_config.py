import pytest
from pydantic import ValidationError

from giftai.core.config import Environment, Settings


@pytest.mark.parametrize(
    "raw_url",
    [
        "postgres://user:pass@db.example.com:5432/giftai?sslmode=require",
        "postgresql://user:pass@db.example.com:5432/giftai?sslmode=require",
        "postgresql+psycopg://user:pass@db.example.com:5432/giftai?sslmode=require",
    ],
)
def test_database_url_is_normalised_to_the_psycopg_driver(raw_url: str) -> None:
    settings = Settings(database_url=raw_url)  # type: ignore[arg-type]

    assert settings.sqlalchemy_database_url == (
        "postgresql+psycopg://user:pass@db.example.com:5432/giftai?sslmode=require"
    )


def test_database_url_must_be_postgres() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="mysql://user:pass@localhost/giftai")  # type: ignore[arg-type]


def test_database_password_is_hidden_from_reprs() -> None:
    settings = Settings(database_url="postgresql://user:hunter2@localhost/giftai")  # type: ignore[arg-type]

    assert "hunter2" not in repr(settings)


def test_cors_origins_accept_a_comma_separated_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/giftai")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:4200, https://giftai.vercel.app")

    settings = Settings()

    assert settings.cors_allowed_origins == [
        "http://localhost:4200",
        "https://giftai.vercel.app",
    ]


def test_production_flag_follows_environment() -> None:
    url = "postgresql://user:pass@localhost/giftai"

    assert Settings(database_url=url, environment=Environment.PRODUCTION).is_production  # type: ignore[arg-type]
    assert not Settings(database_url=url).is_production  # type: ignore[arg-type]

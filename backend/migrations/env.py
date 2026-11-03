"""Alembic environment: runs migrations with the app's own settings and model metadata."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from giftai.core.config import get_database_settings
from giftai.db import models  # noqa: F401  # registers every model on Base.metadata
from giftai.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    # Migrations are a one-off batch job, so a plain synchronous connection is enough.
    engine = create_engine(get_database_settings().sqlalchemy_database_url)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (SQL script) migrations are not supported; run against a database.")

run_migrations_online()

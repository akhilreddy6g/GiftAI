"""Checks whether the backend's dependencies are reachable and correctly set up."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from giftai.db.session import Database
from giftai.health.schemas import CheckStatus, ReadinessReport

logger = logging.getLogger(__name__)

_VECTOR_EXTENSION_INSTALLED = text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")


class HealthService:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def check_readiness(self) -> ReadinessReport:
        """Report on the database and pgvector, never raising.

        This query is also what the scheduled keep-alive ping runs, so the free database
        host sees regular activity and doesn't power the instance off.
        """
        try:
            async with self._database.engine.connect() as connection:
                vector_installed = (await connection.execute(_VECTOR_EXTENSION_INSTALLED)).first()
        except (SQLAlchemyError, OSError):
            logger.exception("Readiness check could not reach the database")
            return ReadinessReport(
                status=CheckStatus.FAILING,
                database=CheckStatus.FAILING,
                vector_extension=CheckStatus.FAILING,
            )

        vector_status = CheckStatus.OK if vector_installed else CheckStatus.FAILING
        if vector_status is CheckStatus.FAILING:
            logger.error("pgvector extension is missing; run the database migrations")
        return ReadinessReport(
            status=vector_status, database=CheckStatus.OK, vector_extension=vector_status
        )

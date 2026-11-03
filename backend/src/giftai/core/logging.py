"""Logging setup: readable text locally, one JSON object per line in production.

Each log record carries the current request id (see ``request_context``) so the lines
belonging to one failing request can be found together in the host's log viewer.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import override

from giftai.core.config import LogFormat
from giftai.core.request_context import get_request_id

# Attributes every LogRecord has; anything else was passed through ``extra=`` and is kept.
_STANDARD_RECORD_ATTRIBUTES = frozenset(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class _RequestIdFilter(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


class _JsonFormatter(logging.Formatter):
    @override
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(
            {
                key: value
                for key, value in vars(record).items()
                if key not in _STANDARD_RECORD_ATTRIBUTES
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s"


def configure_logging(level: str, log_format: LogFormat) -> None:
    """Route all logging (ours, uvicorn's, SQLAlchemy's) through one stdout handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(
        _JsonFormatter() if log_format is LogFormat.JSON else logging.Formatter(_TEXT_FORMAT)
    )

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())

    # Uvicorn installs its own handlers; let its records flow to ours instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

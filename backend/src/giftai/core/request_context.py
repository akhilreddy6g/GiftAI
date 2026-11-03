"""Per-request context shared between middleware, logging and error responses.

The server runs each request in its own asyncio task, and every task gets a copy of the
context, so a value set while handling one request never leaks into another.
"""

from contextvars import ContextVar

REQUEST_ID_HEADER = "X-Request-ID"

_NO_REQUEST = "-"

_request_id: ContextVar[str] = ContextVar("request_id", default=_NO_REQUEST)


def get_request_id() -> str:
    """The id of the request being handled, or ``-`` outside of a request."""
    return _request_id.get()


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)

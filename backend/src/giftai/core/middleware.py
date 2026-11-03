"""ASGI middleware that wraps every request."""

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from giftai.core.request_context import REQUEST_ID_HEADER, set_request_id

logger = logging.getLogger(__name__)

# A caller-supplied id is reused only if it looks harmless, so it can't inject into logs.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class RequestIdMiddleware:
    """Gives each request an id, echoes it in the response and logs the request's outcome."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = self._incoming_request_id(scope) or uuid.uuid4().hex
        set_request_id(request_id)
        started_at = time.perf_counter()
        status_code = 500  # Reported if the app crashes before sending a response.

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self._app(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "%s %s -> %d",
                scope["method"],
                scope["path"],
                status_code,
                extra={"duration_ms": round((time.perf_counter() - started_at) * 1000, 1)},
            )

    @staticmethod
    def _incoming_request_id(scope: Scope) -> str | None:
        header_name = REQUEST_ID_HEADER.lower().encode()
        for name, value in scope["headers"]:
            if name == header_name:
                candidate = value.decode("latin-1")
                return candidate if _SAFE_REQUEST_ID.fullmatch(candidate) else None
        return None

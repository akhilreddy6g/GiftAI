"""ASGI middleware that wraps every request."""

import contextlib
import logging
import re
import time
import uuid
from http import HTTPStatus

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from giftai.core.errors import build_error_response
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


class _BodyTooLargeError(Exception):
    pass


class BodySizeLimitMiddleware:
    """Rejects request bodies over ``max_bytes`` with 413, before the app reads them.

    Checks the declared Content-Length up front, and also counts streamed chunks, since a
    client can omit or understate the header.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        declared_length = Headers(scope=scope).get("content-length")
        if (
            declared_length is not None
            and declared_length.isdigit()
            and int(declared_length) > self._max_bytes
        ):
            await self._reject(scope, receive, send)
            return

        received_bytes = 0
        too_large = False
        response_started = False

        async def receive_within_limit() -> Message:
            nonlocal received_bytes, too_large
            message = await receive()
            if message["type"] == "http.request":
                received_bytes += len(message.get("body", b""))
                if received_bytes > self._max_bytes:
                    too_large = True
                    raise _BodyTooLargeError
            return message

        async def send_unless_rejected(message: Message) -> None:
            nonlocal response_started
            # The framework may turn our exception into its own error response; ours wins.
            if too_large:
                return
            response_started = response_started or message["type"] == "http.response.start"
            await send(message)

        with contextlib.suppress(_BodyTooLargeError):
            await self._app(scope, receive_within_limit, send_unless_rejected)
        if too_large and not response_started:
            await self._reject(scope, receive, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = build_error_response(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "payload_too_large",
            "That request is too large. Please shorten it and try again.",
        )
        await response(scope, receive, send)

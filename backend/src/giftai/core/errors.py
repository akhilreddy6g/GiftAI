"""The application's error vocabulary and how each error becomes an HTTP response.

Code anywhere in the app raises an ``AppError`` subclass; it never builds error responses
itself. The handlers registered here turn every failure (ours, validation, routing or an
unexpected crash) into the same JSON envelope, so the frontend handles errors one way:

    {"error": {"code": "not_found", "message": "...", "request_id": "..."}}

Messages are written for end users. Causes are logged, never sent to the client.
"""

import logging
from http import HTTPStatus
from typing import ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from giftai.core.request_context import REQUEST_ID_HEADER, get_request_id

logger = logging.getLogger(__name__)


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class AppError(Exception):
    """Base class for failures the app expects and can explain to the user."""

    status: ClassVar[HTTPStatus] = HTTPStatus.INTERNAL_SERVER_ERROR
    code: ClassVar[str] = "internal_error"
    default_message: ClassVar[str] = "Something went wrong on our side. Please try again."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(AppError):
    status = HTTPStatus.NOT_FOUND
    code = "not_found"
    default_message = "We couldn't find what you were looking for."


class ConflictError(AppError):
    status = HTTPStatus.CONFLICT
    code = "conflict"
    default_message = "That change conflicts with the current state. Refresh and try again."


class ServiceUnavailableError(AppError):
    """A dependency (database, LLM, auth provider) is down or over its limits."""

    status = HTTPStatus.SERVICE_UNAVAILABLE
    code = "service_unavailable"
    default_message = "GiftAI is temporarily unavailable. Please try again in a minute."


def build_error_response(status: HTTPStatus, code: str, message: str) -> JSONResponse:
    request_id = get_request_id()
    body = ErrorResponse(error=ErrorBody(code=code, message=message, request_id=request_id))
    # Set here too because crash responses are built outside the request-id middleware.
    return JSONResponse(
        status_code=status, content=body.model_dump(), headers={REQUEST_ID_HEADER: request_id}
    )


async def _handle_app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101  # guaranteed by the registration below
    log_level = logging.ERROR if exc.status >= HTTPStatus.INTERNAL_SERVER_ERROR else logging.INFO
    logger.log(log_level, "%s: %s", exc.code, exc.message, exc_info=exc.__cause__)
    return build_error_response(exc.status, exc.code, exc.message)


async def _handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    # Point at the first offending field; the full list is noise for an end user.
    first_error = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first_error.get("loc", ()) if part != "body")
    detail = first_error.get("msg", "Invalid input")
    message = f"{location}: {detail}" if location else detail
    return build_error_response(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_request", message)


async def _handle_http_error(_: Request, exc: Exception) -> JSONResponse:
    """Routing-level errors raised by the framework itself, such as 404 and 405."""
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    status = HTTPStatus(exc.status_code)
    return build_error_response(status, status.name.lower(), status.phrase)


async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return build_error_response(AppError.status, AppError.code, AppError.default_message)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)

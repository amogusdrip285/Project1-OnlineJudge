"""Error envelope for every non-2xx response: {"error": {"code": ..., "message": ...}}.

Codes are listed in MASTER_PLAN §6.1. Raise `AppError` from services/routers for expected errors.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

STATUS_TO_CODE: dict[int, str] = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "SOURCE_TOO_LARGE",
    429: "RATE_LIMITED",
}
DEFAULT_MESSAGES: dict[int, str] = {
    401: "Not authenticated",
    403: "Not allowed",
    404: "Not found",
    405: "Method not allowed",
}


class AppError(Exception):
    """An expected error that is shown to the client as-is."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def _describe_validation_error(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid request"
    first = errors[0]
    # loc is like ("path", "item_id") or ("body", "language"); skip the location kind.
    field = ".".join(str(part) for part in first.get("loc", ())[1:])
    message = first.get("msg", "Invalid value")
    return f"{field}: {message}" if field else message


async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message)


async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = STATUS_TO_CODE.get(exc.status_code, "ERROR")
    if isinstance(exc.detail, str) and exc.detail:
        message = exc.detail
    else:
        message = DEFAULT_MESSAGES.get(exc.status_code, "Request failed")
    return error_response(exc.status_code, code, message)


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(400, "VALIDATION_ERROR", _describe_validation_error(exc))


async def _handle_data_error(request: Request, exc: DataError) -> JSONResponse:
    # The DB refused a value (out of range, bad encoding): the client's input, not our bug.
    logger.warning("Rejected input on %s %s: %s", request.method, request.url.path, exc.orig)
    return error_response(400, "VALIDATION_ERROR", "Invalid input value")


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return error_response(500, "INTERNAL_ERROR", "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(DataError, _handle_data_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)

"""Consistent JSON error responses."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import redact_secrets
from app.schemas.errors import ErrorBody

logger = logging.getLogger(__name__)

_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "too_many_requests",
    503: "service_unavailable",
}


def _status_error_code(status_code: int) -> str:
    return _ERROR_CODES.get(status_code, "request_error")


def _error_response(status_code: int, error: str, message: str, details: Any | None = None) -> JSONResponse:
    body = ErrorBody(error=error, message=message, details=details)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _validation_details(exc: RequestValidationError) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    for error in exc.errors():
        details.append(
            {
                "loc": error.get("loc"),
                "msg": error.get("msg"),
                "type": error.get("type"),
            }
        )
    return details


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers that hide internal failures and keep one error shape."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        del request
        if isinstance(exc.detail, str):
            message = exc.detail
            details = None
        else:
            message = "Request failed"
            details = exc.detail
        return _error_response(exc.status_code, _status_error_code(exc.status_code), message, details)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        del request
        return _error_response(
            422,
            "validation_error",
            "Request validation failed",
            _validation_details(exc),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled error on %s %s: %s",
            request.method,
            request.url.path,
            redact_secrets(str(exc)),
        )
        return _error_response(
            500,
            "internal_error",
            "An unexpected error occurred",
            None,
        )

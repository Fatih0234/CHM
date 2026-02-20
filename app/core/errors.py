"""API error envelope and exception handler registration."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI
from fastapi import Request
from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.error import ErrorDetail
from app.schemas.error import ErrorObject
from app.schemas.error import ErrorResponse


class APIError(Exception):
    """Base application exception for explicit API error responses."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Sequence[ErrorDetail] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = list(details) if details else None


class NotFoundError(APIError):
    """Convenience exception for missing resources."""

    def __init__(self, *, message: str = "Resource not found") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, code="not_found", message=message)


def _build_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Sequence[ErrorDetail] | None = None,
) -> JSONResponse:
    payload = ErrorResponse(error=ErrorObject(code=code, message=message, details=list(details) if details else None))
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


def _http_error_code(status_code: int) -> str:
    if status_code == status.HTTP_404_NOT_FOUND:
        return "not_found"
    if status_code == status.HTTP_400_BAD_REQUEST:
        return "validation_error"
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "unauthorized"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "forbidden"
    if status_code == status.HTTP_409_CONFLICT:
        return "conflict"
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return "internal_error"
    return "bad_request"


def _validation_details(exc: RequestValidationError) -> list[ErrorDetail]:
    details: list[ErrorDetail] = []
    for issue in exc.errors():
        location = issue.get("loc", ())
        field = _format_location(location)
        message = str(issue.get("msg", "Invalid value"))
        details.append(ErrorDetail(field=field, issue=message))
    return details


def _format_location(location: tuple[Any, ...] | list[Any] | Any) -> str:
    if not isinstance(location, (tuple, list)):
        return str(location)

    prefixes = {"body", "query", "path", "header", "cookie"}
    filtered = [str(part) for part in location if part not in prefixes]
    if filtered:
        return ".".join(filtered)

    if not location:
        return "request"

    return str(location[0])


async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Normalize FastAPI validation errors to the CHM error envelope."""

    return _build_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        code="validation_error",
        message="Request validation failed",
        details=_validation_details(exc),
    )


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Normalize HTTP exceptions to the CHM error envelope."""

    details: Sequence[ErrorDetail] | None = None

    if isinstance(exc.detail, dict):
        detail = exc.detail
        if "error" in detail and isinstance(detail["error"], dict):
            error = detail["error"]
            code = str(error.get("code", _http_error_code(exc.status_code)))
            message = str(error.get("message", "Request failed"))
            raw_details = error.get("details")
            if isinstance(raw_details, list):
                details = [
                    ErrorDetail(field=str(item.get("field", "request")), issue=str(item.get("issue", "Invalid value")))
                    for item in raw_details
                    if isinstance(item, dict)
                ]
            return _build_error_response(
                status_code=exc.status_code,
                code=code,
                message=message,
                details=details,
            )

        if "code" in detail and "message" in detail:
            code = str(detail.get("code"))
            message = str(detail.get("message"))
            raw_details = detail.get("details")
            if isinstance(raw_details, list):
                details = [
                    ErrorDetail(field=str(item.get("field", "request")), issue=str(item.get("issue", "Invalid value")))
                    for item in raw_details
                    if isinstance(item, dict)
                ]
            return _build_error_response(
                status_code=exc.status_code,
                code=code,
                message=message,
                details=details,
            )

    message = str(exc.detail) if isinstance(exc.detail, str) and exc.detail else "Request failed"
    return _build_error_response(
        status_code=exc.status_code,
        code=_http_error_code(exc.status_code),
        message=message,
    )


async def api_error_handler(_: Request, exc: APIError) -> JSONResponse:
    """Return explicit domain errors in the shared envelope."""

    return _build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def unhandled_exception_handler(_: Request, __: Exception) -> JSONResponse:
    """Avoid leaking internal exceptions while keeping response shape stable."""

    return _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
        message="Internal server error",
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach all CHM error handlers to a FastAPI app instance."""

    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

"""Transport-level error handlers mapping domain exceptions to HTTP responses."""

import logging
lazy from collections.abc import Mapping

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.exceptions import (
    AuthenticationRequiredError,
    BusinessRuleViolationError,
    CustomError,
    DuplicateEntityError,
    EntityNotFoundError,
    ExternalServiceError,
    PermissionDeniedError,
)
from app.infrastructure.telemetry.logging import log_operational_event

logger = logging.getLogger("app.presentation.exception_handlers")

type ErrorStatusMap = Mapping[type[CustomError], int]

ERROR_STATUS_MAP: ErrorStatusMap = frozendict(
    {
        EntityNotFoundError: status.HTTP_404_NOT_FOUND,
        AuthenticationRequiredError: status.HTTP_401_UNAUTHORIZED,
        PermissionDeniedError: status.HTTP_403_FORBIDDEN,
        DuplicateEntityError: status.HTTP_409_CONFLICT,
        BusinessRuleViolationError: status.HTTP_400_BAD_REQUEST,
        ExternalServiceError: status.HTTP_502_BAD_GATEWAY,
    }
)


def resolve_status_code(exc: CustomError) -> int:
    """Performs type-based lookup for domain exception HTTP status code."""
    for exc_type, status_code in ERROR_STATUS_MAP.items():
        if isinstance(exc, exc_type):
            return status_code
    return status.HTTP_400_BAD_REQUEST


async def domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Unified handler that maps any CustomError to its corresponding HTTP response."""
    if isinstance(exc, CustomError):
        status_code = resolve_status_code(exc)
        public_details: dict[str, object] = (
            {}
            if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
            or isinstance(exc, ExternalServiceError)
            else dict(exc.details)
        )
        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.name,
                "message": exc.message,
                "details": public_details,
            },
        )
    log_operational_event(
        logger,
        event="request.unhandled_exception",
        status="failure",
        message="Unhandled exception in request handler",
        exception_type=type(exc).__name__,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred.",
            "details": {},
        },
    )


async def http_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Formats Starlette/FastAPI HTTPException using the unified error JSON envelope."""
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTPException",
                "message": str(exc.detail),
                "details": {},
            },
            headers=exc.headers,
        )
    return await domain_error_handler(_request, exc)


def register_exception_handlers(app: FastAPI) -> None:
    """Registers unified domain and HTTP exception handlers."""
    app.add_exception_handler(CustomError, domain_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)


__all__ = [
    "ERROR_STATUS_MAP",
    "ErrorStatusMap",
    "domain_error_handler",
    "http_exception_handler",
    "register_exception_handlers",
    "resolve_status_code",
]

"""Transport-level error handlers mapping domain exceptions to HTTP responses."""

lazy from collections.abc import Mapping

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    AuthenticationRequiredError,
    BusinessRuleViolationError,
    CustomError,
    DuplicateEntityError,
    EntityNotFoundError,
    ExternalServiceError,
    PermissionDeniedError,
)

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
        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.name,
                "message": exc.message,
                "details": exc.details,
            },
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "InternalServerError", "message": str(exc)},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers unified domain exception handler for CustomError and all mapped subclasses."""
    app.add_exception_handler(CustomError, domain_error_handler)
    for exc_cls in ERROR_STATUS_MAP:
        app.add_exception_handler(exc_cls, domain_error_handler)


__all__ = [
    "ERROR_STATUS_MAP",
    "ErrorStatusMap",
    "domain_error_handler",
    "register_exception_handlers",
    "resolve_status_code",
]

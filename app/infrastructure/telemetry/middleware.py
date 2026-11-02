"""ASGI and Starlette HTTP middleware for correlation ID tracking and request telemetry."""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
lazy from fastapi import Request
lazy from starlette.middleware.base import RequestResponseEndpoint

from app.infrastructure.telemetry.logging import (
    log_operational_event,
    reset_correlation_id,
    set_correlation_id,
)

logger = logging.getLogger("app.telemetry.middleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware extracting or generating correlation IDs and logging request telemetry."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Processes request lifecycle with correlation tracking and operational logging."""
        correlation_id = (
            request.headers.get("x-correlation-id")
            or request.headers.get("x-request-id")
            or uuid.uuid4().hex
        )
        token = set_correlation_id(correlation_id)

        client_host = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        log_operational_event(
            logger,
            event="request.start",
            status="started",
            message=f"Request started: {method} {path}",
            method=method,
            path=path,
            client_host=client_host,
        )

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001 - outer gateway request boundary
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            log_operational_event(
                logger,
                event="request.failure",
                status="failure",
                message=f"Request failed with exception: {method} {path}",
                method=method,
                path=path,
                status_code=500,
                duration_ms=duration_ms,
                exception_type=type(exc).__name__,
                exc_info=exc,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred",
                },
                headers={"X-Correlation-Id": correlation_id},
            )
        else:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            response.headers["X-Correlation-Id"] = correlation_id

            if response.status_code >= 500:
                log_operational_event(
                    logger,
                    event="request.failure",
                    status="failure",
                    message=f"Request failed with status {response.status_code}: {method} {path}",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )
            else:
                log_operational_event(
                    logger,
                    event="request.success",
                    status="success",
                    message=f"Request completed: {method} {path} - {response.status_code}",
                    method=method,
                    path=path,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )
            return response
        finally:
            reset_correlation_id(token)


__all__ = ["CorrelationIdMiddleware"]

"""Pure ASGI HTTP middleware for correlation ID tracking and request telemetry."""

import logging
import time
import uuid

from starlette.responses import JSONResponse
lazy from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.infrastructure.telemetry.logging import (
    log_operational_event,
    reset_correlation_id,
    set_correlation_id,
)

logger = logging.getLogger("app.presentation.middleware")


def _extract_correlation_id(headers: list[tuple[bytes, bytes]]) -> str:
    found: dict[str, str] = {}
    for raw_key, raw_val in headers:
        key = raw_key.decode("latin-1").lower()
        if key in ("x-correlation-id", "x-request-id") and key not in found:
            val = raw_val.decode("latin-1").strip()
            if val:
                found[key] = val
    return (
        found.get("x-correlation-id") or found.get("x-request-id") or uuid.uuid4().hex
    )


def _upsert_correlation_header(
    headers: list[tuple[bytes, bytes]], correlation_id: str
) -> list[tuple[bytes, bytes]]:
    filtered = [(k, v) for k, v in headers if k.lower() != b"x-correlation-id"]
    filtered.append((b"x-correlation-id", correlation_id.encode("latin-1")))
    return filtered


def _log_response_event(
    method: str, path: str, status_code: int, duration_ms: float
) -> None:
    if status_code >= 500:
        log_operational_event(
            logger,
            event="request.failure",
            status="failure",
            message=f"Request failed with status {status_code}: {method} {path}",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
    elif status_code >= 400:
        log_operational_event(
            logger,
            event="request.client_error",
            status="warning",
            message=f"Request client error {status_code}: {method} {path}",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
    else:
        log_operational_event(
            logger,
            event="request.success",
            status="success",
            message=f"Request completed: {method} {path} - {status_code}",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
        )


class CorrelationIdMiddleware:
    """Pure ASGI middleware tracking correlation IDs and structured request telemetry."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = _extract_correlation_id(scope.get("headers", []))
        token = set_correlation_id(correlation_id)
        client = scope.get("client")
        client_host = client[0] if client else "unknown"
        method = scope.get("method", "GET")
        path = scope.get("path", "/")

        log_operational_event(
            logger,
            event="request.start",
            status="started",
            message=f"Request started: {method} {path}",
            method=method,
            path=path,
            client_host=client_host,
        )

        status_code = 500
        response_started = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = int(message["status"])
                message = {
                    **message,
                    "headers": _upsert_correlation_header(
                        list(message.get("headers", [])), correlation_id
                    ),
                }
            await send(message)

        start_time = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
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
            if response_started:
                raise
            response = JSONResponse(
                status_code=500,
                content={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred.",
                    "details": {},
                },
                headers={"X-Correlation-Id": correlation_id},
            )
            await response(scope, receive, send)
        else:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            _log_response_event(method, path, status_code, duration_ms)
        finally:
            reset_correlation_id(token)


__all__ = ["CorrelationIdMiddleware"]

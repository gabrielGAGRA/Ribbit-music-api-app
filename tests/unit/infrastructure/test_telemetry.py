"""Unit tests for structured logging, correlation ID tracking, and operational events."""

import json
import logging
import sys
import uuid

import pytest
from fastapi import Request
from starlette.responses import JSONResponse, Response

from app.composition import create_app
from app.config import Settings
from app.infrastructure.telemetry.logging import (
    JSONLogFormatter,
    configure_logging,
    correlation_id_ctx,
    get_correlation_id,
    log_operational_event,
    set_correlation_id,
)
from app.infrastructure.telemetry.middleware import CorrelationIdMiddleware


class LogCaptureHandler(logging.Handler):
    """Logging handler capturing emitted records and their formatted JSON output."""

    def __init__(self, formatter: logging.Formatter | None = None) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []
        self.formatted_lines: list[str] = []
        if formatter:
            self.setFormatter(formatter)

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
        if self.formatter:
            self.formatted_lines.append(self.format(record))


def _make_dummy_request(
    path: str = "/test",
    method: str = "GET",
    headers: list[tuple[bytes, bytes]] | None = None,
    client: tuple[str, int] = ("127.0.0.1", 50000),
) -> Request:
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [],
        "client": client,
    }
    return Request(scope)


@pytest.mark.unit
def test_json_log_formatter_standard_fields() -> None:
    formatter = JSONLogFormatter()
    record = logging.makeLogRecord(
        {
            "name": "app.test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "Hello structured logs",
            "event": "service.startup",
        }
    )

    output = formatter.format(record)
    data = json.loads(output)

    assert "timestamp" in data
    assert data["level"] == "INFO"
    assert data["logger"] == "app.test"
    assert data["message"] == "Hello structured logs"
    assert data["event"] == "service.startup"
    assert "correlation_id" not in data


@pytest.mark.unit
def test_json_log_formatter_sensitive_fields_redaction() -> None:
    formatter = JSONLogFormatter()
    record = logging.makeLogRecord(
        {
            "name": "app.security",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "Payload sanitization check",
            "password": "plain-text-password",
            "access_token": "secret-token-123",
            "client_secret": "my-secret-key",
            "authorization": "Bearer xyz",
            "api_key": "raw-key-value",
            "apikey": "raw-apikey-value",
            "nested": {
                "user_token": "nested-token",
                "public_field": "visible",
                "inner": {"deep_password": "nested-pass"},
            },
            "credentials_list": [{"password": "pw_in_list"}, "safe_item"],
        }
    )

    output = formatter.format(record)
    data = json.loads(output)

    assert data["password"] == "[REDACTED]"
    assert data["access_token"] == "[REDACTED]"
    assert data["client_secret"] == "[REDACTED]"
    assert data["authorization"] == "[REDACTED]"
    assert data["api_key"] == "[REDACTED]"
    assert data["apikey"] == "[REDACTED]"
    assert data["nested"]["user_token"] == "[REDACTED]"
    assert data["nested"]["public_field"] == "visible"
    assert data["nested"]["inner"]["deep_password"] == "[REDACTED]"
    assert data["credentials_list"][0]["password"] == "[REDACTED]"
    assert data["credentials_list"][1] == "safe_item"


@pytest.mark.unit
def test_json_log_formatter_correlation_id_from_context() -> None:
    formatter = JSONLogFormatter()

    token = set_correlation_id("test-corr-456")
    try:
        record = logging.makeLogRecord(
            {
                "name": "app.test",
                "levelno": logging.INFO,
                "levelname": "INFO",
                "msg": "With correlation ID",
            }
        )
        data = json.loads(formatter.format(record))
        assert data["correlation_id"] == "test-corr-456"
    finally:
        correlation_id_ctx.reset(token)

    record_no_id = logging.makeLogRecord(
        {
            "name": "app.test",
            "levelno": logging.INFO,
            "levelname": "INFO",
            "msg": "Without correlation ID",
        }
    )
    data_no_id = json.loads(formatter.format(record_no_id))
    assert "correlation_id" not in data_no_id


@pytest.mark.unit
def test_json_log_formatter_duration_and_exception() -> None:
    formatter = JSONLogFormatter()

    def _raise_error() -> None:
        raise ValueError("Something went wrong")

    try:
        _raise_error()
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.makeLogRecord(
        {
            "name": "app.test",
            "levelno": logging.ERROR,
            "levelname": "ERROR",
            "msg": "Failure occurred",
            "duration_ms": 12.34,
            "exc_info": exc_info,
        }
    )

    data = json.loads(formatter.format(record))
    assert data["duration_ms"] == 12.34
    assert "exception" in data
    assert "ValueError: Something went wrong" in data["exception"]


@pytest.mark.unit
def test_log_operational_event_helper() -> None:
    capture = LogCaptureHandler(formatter=JSONLogFormatter())
    test_logger = logging.getLogger("test.operational.events")
    test_logger.setLevel(logging.DEBUG)
    test_logger.addHandler(capture)

    try:
        log_operational_event(
            test_logger,
            event="order.created",
            status="success",
            message="Order processed successfully",
            order_id="1001",
        )
        assert len(capture.records) == 1
        record = capture.records[0]
        assert record.levelname == "INFO"
        data = json.loads(capture.formatted_lines[0])
        assert data["event"] == "order.created"
        assert data["status"] == "success"
        assert data["order_id"] == "1001"

        log_operational_event(
            test_logger,
            event="payment.charge",
            status="failure",
            message="Card expired",
            card_token="tok_123",
        )
        assert len(capture.records) == 2
        fail_record = capture.records[1]
        assert fail_record.levelname == "ERROR"
        fail_data = json.loads(capture.formatted_lines[1])
        assert fail_data["event"] == "payment.charge"
        assert fail_data["status"] == "failure"
        assert fail_data["card_token"] == "[REDACTED]"
    finally:
        test_logger.removeHandler(capture)


@pytest.mark.unit
def test_configure_logging() -> None:
    target_logger = logging.getLogger("app")
    prev_level = target_logger.level
    prev_propagate = target_logger.propagate
    prev_handlers = list(target_logger.handlers)
    try:
        app_logger = configure_logging("DEBUG")
        assert app_logger.level == logging.DEBUG
        assert len(app_logger.handlers) == 1
        assert isinstance(app_logger.handlers[0].formatter, JSONLogFormatter)
    finally:
        target_logger.setLevel(prev_level)
        target_logger.propagate = prev_propagate
        target_logger.handlers = prev_handlers


@pytest.mark.unit
@pytest.mark.anyio
async def test_correlation_id_middleware_generates_id() -> None:
    async def downstream_app(_request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    middleware = CorrelationIdMiddleware(downstream_app)
    req = _make_dummy_request(path="/api/test")

    response = await middleware.dispatch(req, downstream_app)

    assert "X-Correlation-Id" in response.headers
    corr_id = response.headers["X-Correlation-Id"]
    assert len(corr_id) == 32
    uuid_obj = uuid.UUID(hex=corr_id)
    assert uuid_obj.hex == corr_id


@pytest.mark.unit
@pytest.mark.anyio
async def test_correlation_id_middleware_reuses_incoming_x_correlation_id() -> None:
    async def downstream_app(_request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    middleware = CorrelationIdMiddleware(downstream_app)
    req = _make_dummy_request(headers=[(b"x-correlation-id", b"custom-trace-id-123")])

    response = await middleware.dispatch(req, downstream_app)

    assert response.headers["X-Correlation-Id"] == "custom-trace-id-123"


@pytest.mark.unit
@pytest.mark.anyio
async def test_correlation_id_middleware_reuses_incoming_x_request_id() -> None:
    async def downstream_app(_request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    middleware = CorrelationIdMiddleware(downstream_app)
    req = _make_dummy_request(headers=[(b"x-request-id", b"incoming-request-abc")])

    response = await middleware.dispatch(req, downstream_app)

    assert response.headers["X-Correlation-Id"] == "incoming-request-abc"


@pytest.mark.unit
@pytest.mark.anyio
async def test_correlation_id_middleware_sets_and_cleans_contextvar() -> None:
    captured_context_id: list[str | None] = []

    async def downstream_app(_request: Request) -> Response:
        captured_context_id.append(get_correlation_id())
        return JSONResponse({"status": "ok"})

    middleware = CorrelationIdMiddleware(downstream_app)
    req = _make_dummy_request(headers=[(b"x-correlation-id", b"ctx-test-id")])

    assert get_correlation_id() is None
    response = await middleware.dispatch(req, downstream_app)

    assert response.headers["X-Correlation-Id"] == "ctx-test-id"
    assert captured_context_id == ["ctx-test-id"]
    assert get_correlation_id() is None


@pytest.mark.unit
@pytest.mark.anyio
async def test_correlation_id_middleware_captures_unhandled_exception() -> None:
    async def failing_app(_request: Request) -> Response:
        raise RuntimeError("Downstream service failure")

    middleware = CorrelationIdMiddleware(failing_app)
    req = _make_dummy_request(
        path="/failing", headers=[(b"x-correlation-id", b"err-trace-1")]
    )

    response = await middleware.dispatch(req, failing_app)

    assert response.status_code == 500
    assert response.headers["X-Correlation-Id"] == "err-trace-1"
    assert get_correlation_id() is None


@pytest.mark.unit
@pytest.mark.anyio
async def test_correlation_id_middleware_logs_operational_events() -> None:
    capture = LogCaptureHandler(formatter=JSONLogFormatter())
    telemetry_logger = logging.getLogger("app.telemetry.middleware")
    prev_level = telemetry_logger.level
    telemetry_logger.setLevel(logging.INFO)
    telemetry_logger.addHandler(capture)

    async def successful_app(_request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    async def error_app(_request: Request) -> Response:
        return JSONResponse({"error": "Bad Gateway"}, status_code=502)

    try:
        middleware = CorrelationIdMiddleware(successful_app)
        req = _make_dummy_request(
            path="/users/me", headers=[(b"x-correlation-id", b"log-test-id")]
        )
        await middleware.dispatch(req, successful_app)

        events = [json.loads(line) for line in capture.formatted_lines]
        assert len(events) >= 2
        start_event = events[0]
        success_event = events[1]

        assert start_event["event"] == "request.start"
        assert start_event["method"] == "GET"
        assert start_event["path"] == "/users/me"
        assert start_event["client_host"] == "127.0.0.1"
        assert start_event["correlation_id"] == "log-test-id"

        assert success_event["event"] == "request.success"
        assert success_event["status_code"] == 200
        assert "duration_ms" in success_event

        # Test failure logging
        capture.records.clear()
        capture.formatted_lines.clear()

        middleware_err = CorrelationIdMiddleware(error_app)
        err_req = _make_dummy_request(path="/error")
        await middleware_err.dispatch(err_req, error_app)

        err_events = [json.loads(line) for line in capture.formatted_lines]
        fail_event = err_events[-1]
        assert fail_event["event"] == "request.failure"
        assert fail_event["status_code"] == 502
    finally:
        telemetry_logger.removeHandler(capture)
        telemetry_logger.setLevel(prev_level)


@pytest.mark.unit
@pytest.mark.anyio
async def test_lifespan_startup_and_shutdown_operational_events() -> None:
    capture = LogCaptureHandler(formatter=JSONLogFormatter())
    app_logger = logging.getLogger("app")
    prev_level = app_logger.level
    prev_propagate = app_logger.propagate
    prev_handlers = list(app_logger.handlers)

    test_settings = Settings(
        database_path=":memory:",
        app_title="Ribbit Test App",
        app_version="1.2.3",
        environment="testing",
    )

    try:
        app = create_app(settings=test_settings)
        app_logger.addHandler(capture)

        async with app.router.lifespan_context(app):
            pass

        events = [json.loads(line) for line in capture.formatted_lines]
        startup_events = [e for e in events if e.get("event") == "service.startup"]
        shutdown_events = [e for e in events if e.get("event") == "service.shutdown"]

        assert len(startup_events) == 1
        startup = startup_events[0]
        assert startup["app_title"] == "Ribbit Test App"
        assert startup["app_version"] == "1.2.3"
        assert startup["environment"] == "testing"
        assert "correlation_id" not in startup

        assert len(shutdown_events) == 1
        shutdown = shutdown_events[0]
        assert "Shutting down service" in shutdown["message"]
        assert "correlation_id" not in shutdown
    finally:
        app_logger.setLevel(prev_level)
        app_logger.propagate = prev_propagate
        app_logger.handlers = prev_handlers

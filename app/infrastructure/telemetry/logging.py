"""Structured JSON logging, correlation ID context tracking, and operational events."""

import json
import logging
import sys
from collections.abc import Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any
lazy from contextvars import Token

type LogPayload = dict[str, Any]

SENSITIVE_KEY_PATTERNS: tuple[str, ...] = (
    "password",
    "token",
    "secret",
    "authorization",
    "api_key",
    "apikey",
)

STANDARD_LOG_RECORD_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "id",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)

correlation_id_ctx: ContextVar[str | None] = ContextVar(
    "correlation_id_ctx", default=None
)


def get_correlation_id() -> str | None:
    """Returns the current correlation ID from context."""
    return correlation_id_ctx.get()


def set_correlation_id(val: str | None) -> Token[str | None]:
    """Sets the correlation ID in context and returns the restoration token."""
    return correlation_id_ctx.set(val)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Resets the correlation ID context to a previous state."""
    correlation_id_ctx.reset(token)


def sanitize_payload(obj: Any) -> Any:
    """Recursively masks sensitive values within dictionaries, lists, and tuples."""
    if isinstance(obj, Mapping):
        sanitized: LogPayload = {}
        for key, val in obj.items():
            key_str = str(key).lower()
            if any(pattern in key_str for pattern in SENSITIVE_KEY_PATTERNS):
                sanitized[str(key)] = "[REDACTED]"
            else:
                sanitized[str(key)] = sanitize_payload(val)
        return sanitized
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_payload(item) for item in obj]
    return obj


class JSONLogFormatter(logging.Formatter):
    """Serializes log records into structured single-line JSON."""

    def _extract_extras(self, record: logging.LogRecord) -> LogPayload:
        """Extracts and sanitizes custom extra attributes from the log record."""
        extras: LogPayload = {}
        for key, val in record.__dict__.items():
            if key.startswith("_") or key in STANDARD_LOG_RECORD_ATTRIBUTES:
                continue
            if key in (
                "event",
                "correlation_id",
                "duration_ms",
                "timestamp",
                "level",
                "logger",
                "message",
                "exception",
            ):
                continue
            key_lower = key.lower()
            if any(pattern in key_lower for pattern in SENSITIVE_KEY_PATTERNS):
                extras[key] = "[REDACTED]"
            else:
                extras[key] = sanitize_payload(val)
        return extras

    def format(self, record: logging.LogRecord) -> str:
        """Formats the log record as a structured JSON string."""
        timestamp = (
            datetime.fromtimestamp(record.created, tz=UTC).isoformat()
            if record.created
            else datetime.now(UTC).isoformat()
        )

        data: LogPayload = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        event = getattr(record, "event", None)
        if event is not None:
            data["event"] = str(event)

        cid = getattr(record, "correlation_id", None) or get_correlation_id()
        if cid is not None:
            data["correlation_id"] = str(cid)

        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            data["duration_ms"] = duration_ms

        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        elif record.exc_text:
            data["exception"] = record.exc_text

        data.update(self._extract_extras(record))
        return json.dumps(data, default=str)


def log_operational_event(
    logger: logging.Logger,
    event: str,
    status: str,
    message: str,
    *,
    level: int | None = None,
    **extra: Any,
) -> None:
    """Logs an operational event with consistent vocabulary and metadata."""
    if level is None:
        normalized_status = status.lower()
        if normalized_status in ("failure", "failed", "error"):
            level = logging.ERROR
        elif normalized_status in ("warning", "warn"):
            level = logging.WARNING
        else:
            level = logging.INFO

    exc_info = extra.pop("exc_info", None)
    payload: LogPayload = {"event": event, "status": status, **extra}
    logger.log(level, message, exc_info=exc_info, extra=payload)


def configure_logging(level: str | int = "INFO") -> logging.Logger:
    """Configures structured JSON logging on sys.stdout for application loggers."""
    numeric_level = (
        getattr(logging, level.upper(), logging.INFO)
        if isinstance(level, str)
        else level
    )
    app_logger = logging.getLogger("app")
    app_logger.setLevel(numeric_level)

    for handler in list(app_logger.handlers):
        app_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(numeric_level)
    stream_handler.setFormatter(JSONLogFormatter())
    app_logger.addHandler(stream_handler)
    app_logger.propagate = False

    return app_logger


__all__ = [
    "JSONLogFormatter",
    "LogPayload",
    "configure_logging",
    "correlation_id_ctx",
    "get_correlation_id",
    "log_operational_event",
    "reset_correlation_id",
    "sanitize_payload",
    "set_correlation_id",
]

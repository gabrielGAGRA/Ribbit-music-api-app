"""Unit tests for presentation exception handlers and HTTP status mapping."""

import asyncio
import json
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, Request, status

from app.domain.exceptions import (
    AuthenticationRequiredError,
    BusinessRuleViolationError,
    CustomError,
    DomainError,
    DuplicateEntityError,
    EntityNotFoundError,
    ExternalServiceError,
    PermissionDeniedError,
)
from app.presentation.exception_handlers import (
    ERROR_STATUS_MAP,
    domain_error_handler,
    register_exception_handlers,
    resolve_status_code,
)


@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (
            EntityNotFoundError(entity_name="Track", entity_id=42),
            status.HTTP_404_NOT_FOUND,
        ),
        (
            AuthenticationRequiredError("Missing credentials"),
            status.HTTP_401_UNAUTHORIZED,
        ),
        (
            PermissionDeniedError("Admin only"),
            status.HTTP_403_FORBIDDEN,
        ),
        (
            DuplicateEntityError(entity_name="User", field="email"),
            status.HTTP_409_CONFLICT,
        ),
        (
            BusinessRuleViolationError("Rule broken", rule_name="max_profiles"),
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            ExternalServiceError("Spotify down", service_name="Spotify"),
            status.HTTP_502_BAD_GATEWAY,
        ),
        (
            DomainError("Generic domain error"),
            status.HTTP_400_BAD_REQUEST,
        ),
        (
            CustomError("Base custom error"),
            status.HTTP_400_BAD_REQUEST,
        ),
    ],
)
def test_resolve_status_code_maps_all_domain_exceptions(
    exc: CustomError, expected_status: int
) -> None:
    assert resolve_status_code(exc) == expected_status


def test_domain_error_handler_returns_structured_json_for_entity_not_found() -> None:
    request = MagicMock(spec=Request)
    exc = EntityNotFoundError(entity_name="Playlist", entity_id=99)

    response = asyncio.run(domain_error_handler(request, exc))
    payload = json.loads(bytes(response.body).decode("utf-8"))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert payload == {
        "error": "EntityNotFoundError",
        "message": "Entity 'Playlist' with id '99' not found.",
        "details": {"entity_name": "Playlist", "entity_id": 99},
    }


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_error_name"),
    [
        (
            AuthenticationRequiredError("Token required"),
            status.HTTP_401_UNAUTHORIZED,
            "AuthenticationRequiredError",
        ),
        (
            PermissionDeniedError("Forbidden resource"),
            status.HTTP_403_FORBIDDEN,
            "PermissionDeniedError",
        ),
        (
            DuplicateEntityError(entity_name="User", field="email"),
            status.HTTP_409_CONFLICT,
            "DuplicateEntityError",
        ),
        (
            BusinessRuleViolationError("Premium required", rule_name="premium_only"),
            status.HTTP_400_BAD_REQUEST,
            "BusinessRuleViolationError",
        ),
        (
            ExternalServiceError("Upstream timeout", service_name="iTunes"),
            status.HTTP_502_BAD_GATEWAY,
            "ExternalServiceError",
        ),
        (
            DomainError("Unmapped domain error", details={"reason": "test"}),
            status.HTTP_400_BAD_REQUEST,
            "DomainError",
        ),
        (
            CustomError("Custom failure", name="CustomFailureName"),
            status.HTTP_400_BAD_REQUEST,
            "CustomFailureName",
        ),
    ],
)
def test_domain_error_handler_maps_custom_error_subclasses(
    exc: CustomError, expected_status: int, expected_error_name: str
) -> None:
    request = MagicMock(spec=Request)

    response = asyncio.run(domain_error_handler(request, exc))
    payload = json.loads(bytes(response.body).decode("utf-8"))

    assert response.status_code == expected_status
    assert payload["error"] == expected_error_name
    assert payload["message"] == exc.message
    assert payload["details"] == exc.details


def test_domain_error_handler_fallback_for_non_custom_exception() -> None:
    request = MagicMock(spec=Request)
    exc = RuntimeError("Unexpected crash")

    response = asyncio.run(domain_error_handler(request, exc))
    payload = json.loads(bytes(response.body).decode("utf-8"))

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert payload == {
        "error": "InternalServerError",
        "message": "Unexpected crash",
    }


def test_register_exception_handlers_registers_custom_error_and_all_mapped_types() -> (
    None
):
    app = MagicMock(spec=FastAPI)

    register_exception_handlers(app)

    expected_classes = [CustomError, *ERROR_STATUS_MAP.keys()]
    assert app.add_exception_handler.call_count == len(expected_classes)
    for exc_cls in expected_classes:
        app.add_exception_handler.assert_any_call(exc_cls, domain_error_handler)

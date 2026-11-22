"""Unit tests for the domain exception hierarchy."""

import pytest

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


def test_custom_error_defaults_and_str() -> None:
    err = CustomError("Something went wrong.")
    assert err.message == "Something went wrong."
    assert err.name == "CustomError"
    assert err.details == {}
    assert str(err) == "Something went wrong."


def test_custom_error_custom_name_and_details_copy() -> None:
    raw_details = {"key": "value"}
    err = CustomError("Custom failure", name="SpecificFailure", details=raw_details)
    raw_details["mutated"] = "ignored"
    assert err.message == "Custom failure"
    assert err.name == "SpecificFailure"
    assert err.details == {"key": "value"}


def test_domain_error_inherits_custom_error() -> None:
    err = DomainError("Domain invariant broken", details={"field": "age"})
    assert isinstance(err, CustomError)
    assert err.name == "DomainError"
    assert err.message == "Domain invariant broken"
    assert err.details == {"field": "age"}


def test_entity_not_found_error_default_message_without_context() -> None:
    err = EntityNotFoundError()
    assert isinstance(err, DomainError)
    assert err.name == "EntityNotFoundError"
    assert err.message == "Requested entity was not found."
    assert err.details == {}


def test_entity_not_found_error_with_entity_name_and_id() -> None:
    err = EntityNotFoundError(entity_name="User", entity_id=42)
    assert err.message == "Entity 'User' with id '42' not found."
    assert err.details == {"entity_name": "User", "entity_id": 42}


def test_entity_not_found_error_with_zero_entity_id() -> None:
    err = EntityNotFoundError(entity_name="Track", entity_id=0)
    assert err.message == "Entity 'Track' with id '0' not found."
    assert err.details == {"entity_name": "Track", "entity_id": 0}


def test_entity_not_found_error_with_partial_context_and_custom_message() -> None:
    err = EntityNotFoundError(
        message="Custom not found",
        entity_name="Playlist",
        details={"extra": "info"},
    )
    assert err.message == "Custom not found"
    assert err.details == {"extra": "info", "entity_name": "Playlist"}


def test_business_rule_violation_error_with_and_without_rule_name() -> None:
    err_basic = BusinessRuleViolationError("Cannot exceed max profiles.")
    assert isinstance(err_basic, DomainError)
    assert err_basic.name == "BusinessRuleViolationError"
    assert err_basic.message == "Cannot exceed max profiles."
    assert err_basic.details == {}

    err_named = BusinessRuleViolationError(
        "Track already in playlist.",
        rule_name="unique_playlist_track",
        details={"track_id": 7},
    )
    assert err_named.message == "Track already in playlist."
    assert err_named.details == {
        "rule_name": "unique_playlist_track",
        "track_id": 7,
    }


def test_duplicate_entity_error_defaults_and_formatted_message() -> None:
    err_default = DuplicateEntityError()
    assert isinstance(err_default, DomainError)
    assert err_default.name == "DuplicateEntityError"
    assert err_default.message == "Entity already registered."
    assert err_default.details == {}

    err_ctx = DuplicateEntityError(
        entity_name="User",
        field="email",
        details={"source": "registration"},
    )
    assert err_ctx.message == "Entity 'User' with email already exists."
    assert err_ctx.details == {
        "source": "registration",
        "entity_name": "User",
        "field": "email",
    }

    err_custom = DuplicateEntityError(
        message="Email already taken.",
        entity_name="User",
    )
    assert err_custom.message == "Email already taken."
    assert err_custom.details == {"entity_name": "User"}


def test_external_service_error_defaults_and_service_name() -> None:
    err_default = ExternalServiceError()
    assert isinstance(err_default, DomainError)
    assert err_default.name == "ExternalServiceError"
    assert err_default.message == "External service unavailable or returned an error."
    assert err_default.details == {}

    err_spotify = ExternalServiceError(
        message="Spotify API timed out.",
        service_name="Spotify",
        details={"status_code": 504},
    )
    assert err_spotify.message == "Spotify API timed out."
    assert err_spotify.details == {"service_name": "Spotify", "status_code": 504}


def test_authentication_required_error_defaults_and_custom() -> None:
    err_default = AuthenticationRequiredError()
    assert isinstance(err_default, DomainError)
    assert err_default.name == "AuthenticationRequiredError"
    assert err_default.message == "Authentication required."
    assert err_default.details == {}

    err_custom = AuthenticationRequiredError(
        message="Invalid credentials.",
        details={"reason": "bad_password"},
    )
    assert err_custom.message == "Invalid credentials."
    assert err_custom.details == {"reason": "bad_password"}


def test_permission_denied_error_defaults_and_custom() -> None:
    err_default = PermissionDeniedError()
    assert isinstance(err_default, DomainError)
    assert err_default.name == "PermissionDeniedError"
    assert err_default.message == "Permission denied."
    assert err_default.details == {}

    err_custom = PermissionDeniedError(
        message="Admin privileges required.",
        details={"required_role": "admin"},
    )
    assert err_custom.message == "Admin privileges required."
    assert err_custom.details == {"required_role": "admin"}


def test_exceptions_can_be_raised_and_caught_as_domain_error() -> None:
    with pytest.raises(DomainError) as exc_info:
        raise PermissionDeniedError("Not allowed")
    assert exc_info.value.message == "Not allowed"

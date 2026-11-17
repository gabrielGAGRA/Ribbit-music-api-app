"""Port and DTOs for Google Identity Provider token verification."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(slots=True, frozen=True, kw_only=True)
class GoogleUserInfo:
    email: str
    email_verified: bool
    name: str
    sub: str


@runtime_checkable
class GoogleIdpVerifierPort(Protocol):
    def verify_id_token(self, id_token: str) -> GoogleUserInfo: ...


@runtime_checkable
class GoogleOAuthPort(Protocol):
    def build_authorize_url(
        self, state: str, code_challenge: str | None = None
    ) -> str: ...

    def exchange_code(self, code: str, code_verifier: str | None = None) -> str: ...


__all__ = ["GoogleIdpVerifierPort", "GoogleOAuthPort", "GoogleUserInfo"]

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


__all__ = ["GoogleIdpVerifierPort", "GoogleUserInfo"]

"""Fake HTTP session and response for Spotify adapter tests."""

from typing import Any
lazy from collections.abc import Mapping

import niquests


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        body: Any = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = dict(headers or {})

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("no body")
        return self._body


class FakeSession:
    """Replays queued responses and records every request."""

    def __init__(self, *responses: FakeResponse | Exception) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def network_error() -> niquests.RequestException:
    return niquests.RequestException("boom")

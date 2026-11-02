"""Pure ASGI TestClient implementation for testing FastAPI without external httpx dependency."""

import asyncio
import json as json_lib
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from fastapi import FastAPI


@dataclass(slots=True)
class TestResponse:
    """HTTP response wrapper mimicking standard test client responses."""

    __test__ = False

    status_code: int
    headers: dict[str, str]
    content: bytes

    @property
    def text(self) -> str:
        """Decodes content bytes into UTF-8 string."""
        return self.content.decode("utf-8", errors="replace")

    def json(self) -> Any:
        """Parses response body JSON."""
        return json_lib.loads(self.content.decode("utf-8"))


def _format_query_string(raw_query: str, params: dict[str, Any] | None) -> bytes:
    query_pairs = parse_qsl(raw_query, keep_blank_values=True)
    if params:
        for k, v in params.items():
            if v is not None:
                query_pairs.append((str(k), str(v)))
    return urlencode(query_pairs).encode("ascii")


def _prepare_headers_and_body(
    headers: dict[str, str] | None,
    json_data: Any,
    content: bytes | None,
) -> tuple[list[tuple[bytes, bytes]], bytes]:
    eff_headers = {k.lower(): str(v) for k, v in (headers or {}).items()}
    if json_data is not None and "content-type" not in eff_headers:
        eff_headers["content-type"] = "application/json"
    raw_headers = [
        (k.encode("latin-1"), v.encode("latin-1")) for k, v in eff_headers.items()
    ]

    if json_data is not None:
        body = json_lib.dumps(json_data).encode("utf-8")
    elif content is not None:
        body = content
    else:
        body = b""
    return raw_headers, body


def _create_scope(
    app: FastAPI,
    method: str,
    path: str,
    query_string: bytes,
    headers: list[tuple[bytes, bytes]],
) -> dict[str, Any]:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": query_string,
        "headers": headers,
        "client": ("127.0.0.1", 54321),
        "server": ("testserver", 80),
        "app": app,
        "state": {},
    }


class TestClient:
    """Asynchronous/synchronous ASGI test client executing genuine FastAPI pipelines."""

    __test__ = False

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
        content: bytes | None = None,
    ) -> TestResponse:
        """Dispatches an HTTP request through the ASGI pipeline."""
        parsed = urlsplit(url)
        path = parsed.path or "/"
        query_string = _format_query_string(parsed.query, params)
        raw_headers, body = _prepare_headers_and_body(headers, json, content)
        scope = _create_scope(self.app, method, path, query_string, raw_headers)

        sent_body = False

        async def receive() -> dict[str, Any]:
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }
            return {"type": "http.request", "body": b"", "more_body": False}

        status_code = 500
        resp_headers: dict[str, str] = {}
        body_chunks: list[bytes] = []

        async def send(message: dict[str, Any]) -> None:
            nonlocal status_code, resp_headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                for hk, hv in message.get("headers", []):
                    resp_headers[hk.decode("latin-1").lower()] = hv.decode("latin-1")
            elif message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.app(scope, receive, send))
        finally:
            loop.close()

        return TestResponse(
            status_code=status_code,
            headers=resp_headers,
            content=b"".join(body_chunks),
        )

    def get(self, url: str, **kwargs: Any) -> TestResponse:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> TestResponse:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> TestResponse:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> TestResponse:
        return self.request("DELETE", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> TestResponse:
        return self.request("PATCH", url, **kwargs)


__all__ = ["TestClient", "TestResponse"]

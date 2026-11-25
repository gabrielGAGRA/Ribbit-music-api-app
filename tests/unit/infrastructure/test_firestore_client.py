"""Tests for Firestore REST value conversion and requests."""

import base64
from types import SimpleNamespace
from typing import Any

import pytest

from app.domain.exceptions import ExternalServiceError
from app.infrastructure.adapters.gcp.firestore_client import (
    FirestoreRestClient,
    decode_document,
    decode_firestore_value,
    encode_document_fields,
    encode_firestore_value,
)


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: Any = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> Any:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append((method, url, kwargs))
        if not self.responses:
            raise AssertionError("Unexpected HTTP request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_firestore_values_encode_and_decode_nested_values() -> None:
    value = {
        "none": None,
        "boolean": True,
        "integer": 4,
        "double": 2.5,
        "bytes": b"music",
        "string": "pond",
        "map": {"nested": "value"},
        "array": [False, 3],
        "tuple": ("a", "b"),
        "fallback": object(),
    }

    encoded = encode_document_fields(value)

    assert encoded["none"] == {"nullValue": None}
    assert encoded["boolean"] == {"booleanValue": True}
    assert encoded["integer"] == {"integerValue": "4"}
    assert encoded["double"] == {"doubleValue": 2.5}
    assert encoded["bytes"] == {"bytesValue": base64.b64encode(b"music").decode()}
    assert encoded["map"] == {
        "mapValue": {"fields": {"nested": {"stringValue": "value"}}}
    }
    assert decode_firestore_value(encoded["array"]) == [False, 3]
    assert decode_firestore_value(encoded["tuple"]) == ["a", "b"]
    assert decode_firestore_value({"integerValue": "9"}) == 9
    assert decode_firestore_value({"doubleValue": "2.75"}) == 2.75
    assert decode_firestore_value({"bytesValue": "bXVzaWM="}) == b"music"
    assert decode_firestore_value({"timestampValue": "now"}) == "now"
    assert decode_firestore_value({"missing": True}) is None
    assert encode_firestore_value(object())["stringValue"]


def test_decode_document_includes_document_id_only_when_name_is_valid() -> None:
    assert decode_document(
        {
            "name": "projects/p/databases/d/documents/users/alice",
            "fields": {"active": {"booleanValue": True}},
        }
    ) == {"active": True, "_doc_id": "alice"}
    assert decode_document({"name": "", "fields": {}}) == {}
    assert decode_document({"fields": None}) == {}


def test_firestore_emulator_skips_google_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080/")
    client = FirestoreRestClient(project_id="pond", http_session=FakeSession())

    assert client._base_url == (
        "http://localhost:8080/v1/projects/pond/databases/(default)/documents"
    )
    assert client._auth_headers() == {"Authorization": "Bearer owner"}


def test_firestore_auth_refreshes_and_reuses_application_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    credentials = SimpleNamespace(valid=False, token=None)
    refresh_calls: list[object] = []
    credentials.refresh = lambda request: (
        refresh_calls.append(request),
        setattr(credentials, "valid", True),
        setattr(credentials, "token", "fresh-token"),
    )
    default_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "app.infrastructure.adapters.gcp.firestore_client.google.auth.default",
        lambda **kwargs: (default_calls.append(kwargs) or credentials, "pond"),
    )
    client = FirestoreRestClient(project_id="pond", http_session=FakeSession())

    assert client._auth_headers() == {"Authorization": "Bearer fresh-token"}
    assert client._auth_headers() == {"Authorization": "Bearer fresh-token"}
    assert len(default_calls) == 1
    assert len(refresh_calls) == 1


def test_firestore_request_preserves_domain_errors_and_wraps_transport_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    client = FirestoreRestClient(
        project_id="pond", http_session=FakeSession([RuntimeError("offline")])
    )
    with pytest.raises(ExternalServiceError, match="request failed: offline"):
        client.get_document("users", "alice")

    original = ExternalServiceError("already mapped", service_name="GCP_Firestore")
    client._auth_headers = lambda: (_ for _ in ()).throw(original)
    with pytest.raises(ExternalServiceError, match="already mapped") as exc_info:
        client.get_document("users", "alice")
    assert exc_info.value is original


def test_document_get_upsert_and_delete_status_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    session = FakeSession(
        [
            FakeResponse(404),
            FakeResponse(200, {"fields": {"name": {"stringValue": "Pond"}}}),
            FakeResponse(503, text="x" * 250),
            FakeResponse(204),
            FakeResponse(404),
            FakeResponse(500, text="failure"),
        ]
    )
    client = FirestoreRestClient(project_id="pond", http_session=session)

    assert client.get_document("users", "alice") is None
    assert client.get_document("users", "alice") == {"name": "Pond"}
    with pytest.raises(ExternalServiceError, match="Firestore upsert"):
        client.upsert_document("users", "alice", {"name": "Pond"})
    client.upsert_document("users", "alice", {"name": "Pond"})
    client.delete_document("users", "missing")
    with pytest.raises(ExternalServiceError, match="Firestore delete"):
        client.delete_document("users", "alice")

    assert session.requests[0][0:2] == (
        "GET",
        f"{client._base_url}/users/alice",
    )
    assert session.requests[3][2]["json"]["fields"] == {"name": {"stringValue": "Pond"}}


def test_document_get_and_delete_report_provider_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    client = FirestoreRestClient(
        project_id="pond",
        http_session=FakeSession(
            [FakeResponse(403, text="denied"), FakeResponse(503, text="unavailable")]
        ),
    )
    with pytest.raises(ExternalServiceError, match="Firestore get"):
        client.get_document("users", "alice")
    with pytest.raises(ExternalServiceError, match="Firestore delete"):
        client.delete_document("users", "alice")


def test_list_documents_paginates_and_handles_empty_or_failed_collections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "documents": [
                        {
                            "name": "projects/p/databases/d/documents/users/a",
                            "fields": {"email": {"stringValue": "a"}},
                        }
                    ],
                    "nextPageToken": "next",
                },
            ),
            FakeResponse(
                200,
                {
                    "documents": [
                        {
                            "name": "projects/p/databases/d/documents/users/b",
                            "fields": {"email": {"stringValue": "b"}},
                        }
                    ]
                },
            ),
            FakeResponse(404),
            FakeResponse(503, text="failed"),
        ]
    )
    client = FirestoreRestClient(project_id="pond", http_session=session)

    assert client.list_documents("users", page_size=1) == [
        {"email": "a", "_doc_id": "a"},
        {"email": "b", "_doc_id": "b"},
    ]
    assert session.requests[1][2]["params"]["pageToken"] == "next"
    assert client.list_documents("missing") == []
    with pytest.raises(ExternalServiceError, match="Firestore list"):
        client.list_documents("users")


def test_query_updated_since_uses_list_for_full_sync_and_filters_query_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    session = FakeSession(
        [
            FakeResponse(200, {"documents": []}),
            FakeResponse(
                200,
                [
                    {
                        "document": {
                            "name": "projects/p/databases/d/documents/users/a",
                            "fields": {"updated_at": {"stringValue": "later"}},
                        }
                    },
                    {"readTime": "now"},
                    {"document": "malformed"},
                ],
            ),
            FakeResponse(404),
            FakeResponse(503, text="failed"),
            FakeResponse(200, {"not": "an array"}),
        ]
    )
    client = FirestoreRestClient(project_id="pond", http_session=session)

    assert client.query_updated_since("users") == []
    assert client.query_updated_since("users", "earlier") == [
        {"updated_at": "later", "_doc_id": "a"}
    ]
    assert session.requests[1][0:2] == (
        "POST",
        f"{client._base_url}:runQuery",
    )
    assert client.query_updated_since("users", "earlier") == []
    with pytest.raises(ExternalServiceError, match="Firestore query"):
        client.query_updated_since("users", "earlier")
    with pytest.raises(ExternalServiceError, match="invalid response"):
        client.query_updated_since("users", "earlier")


def test_on_usage_callback_receives_reads_writes_deletes_and_egress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    events: list[tuple[int, int, int, int]] = []
    session = FakeSession(
        [
            FakeResponse(
                200,
                {"fields": {"email": {"stringValue": "a"}}},
                text='{"fields":{"email":{"stringValue":"a"}}}',
            ),
            FakeResponse(
                200,
                {"name": "projects/p/databases/d/documents/users/a"},
                text='{"name":"projects/p/databases/d/documents/users/a"}',
            ),
            FakeResponse(200, {}, text="{}"),
        ]
    )
    client = FirestoreRestClient(
        project_id="pond",
        http_session=session,
        on_usage=lambda *, reads=0, writes=0, deletes=0, egress_bytes=0: events.append(
            (reads, writes, deletes, egress_bytes)
        ),
    )

    assert client.get_document("users", "a") == {"email": "a"}
    client.upsert_document("users", "a", {"email": "a"})
    client.delete_document("users", "a")

    assert [e[:3] for e in events] == [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    assert events[0][3] > 0
    assert client.get_usage_snapshot() == {
        "reads_today": 1,
        "writes_today": 1,
        "deletes_today": 1,
        "egress_bytes_month": sum(e[3] for e in events),
    }

"""REST v1 client for Google Cloud Firestore (Python 3.15 compatible, no gRPC)."""

import base64
import logging
import os
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

import google.auth
import google.auth.transport.requests
import niquests
from google.oauth2 import service_account

from app.domain.exceptions import ExternalServiceError

logger = logging.getLogger("app.infrastructure.firestore_client")

_FIRESTORE_SCOPES = (
    "https://www.googleapis.com/auth/datastore",
    "https://www.googleapis.com/auth/cloud-platform",
)

_SCALAR_DECODERS: dict[str, Callable[[Any], Any]] = {
    "nullValue": lambda _v: None,
    "booleanValue": bool,
    "integerValue": int,
    "doubleValue": float,
    "stringValue": str,
    "timestampValue": str,
    "bytesValue": base64.b64decode,
}


def encode_firestore_value(value: Any) -> dict[str, Any]:
    """Converts a Python value into a Firestore REST Value JSON object."""
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, bytes):
        return {"bytesValue": base64.b64encode(value).decode("ascii")}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, Mapping):
        return {"mapValue": {"fields": encode_document_fields(value)}}
    if isinstance(value, Sequence):
        return {"arrayValue": {"values": [encode_firestore_value(v) for v in value]}}
    return {"stringValue": str(value)}


def encode_document_fields(data: Mapping[str, Any]) -> dict[str, Any]:
    """Converts a flat or nested Python mapping into Firestore REST document fields."""
    return {str(key): encode_firestore_value(val) for key, val in data.items()}


def decode_firestore_value(raw: Mapping[str, Any]) -> Any:
    """Converts a Firestore REST Value JSON object back into a Python value."""
    for key, decoder in _SCALAR_DECODERS.items():
        if key in raw:
            return decoder(raw[key])
    if "arrayValue" in raw:
        items = raw["arrayValue"].get("values") or []
        return [decode_firestore_value(item) for item in items]
    if "mapValue" in raw:
        fields = raw["mapValue"].get("fields") or {}
        return {k: decode_firestore_value(v) for k, v in fields.items()}
    return None


def decode_document(doc: Mapping[str, Any]) -> dict[str, Any]:
    """Converts a Firestore REST Document resource into a Python dictionary."""
    fields = doc.get("fields") or {}
    result: dict[str, Any] = {
        str(key): decode_firestore_value(val) for key, val in fields.items()
    }
    name = doc.get("name")
    if isinstance(name, str) and name:
        result["_doc_id"] = name.rsplit("/", 1)[-1]
    return result


class FirestoreRestClient:
    """Lightweight Firestore v1 REST client with OAuth2 service-account authentication."""

    def __init__(
        self,
        *,
        project_id: str,
        database_id: str = "(default)",
        credentials_path: str | None = None,
        http_session: Any | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._project_id = project_id
        self._database_id = database_id
        self._credentials_path = credentials_path
        self._session = http_session or niquests.Session()
        self._timeout = timeout
        self._credentials: Any | None = None
        self._token_lock = threading.Lock()

        emulator = os.getenv("FIRESTORE_EMULATOR_HOST", "").strip()
        if emulator:
            prefix = "" if emulator.startswith(("http://", "https://")) else "http://"
            host = f"{prefix}{emulator.rstrip('/')}"
            self._base_url = (
                f"{host}/v1/projects/{project_id}/databases/{database_id}/documents"
            )
            self._use_emulator = True
        else:
            self._base_url = (
                f"https://firestore.googleapis.com/v1/projects/{project_id}"
                f"/databases/{database_id}/documents"
            )
            self._use_emulator = False

    def _auth_headers(self) -> dict[str, str]:
        if self._use_emulator:
            return {"Authorization": "Bearer owner"}
        with self._token_lock:
            creds = self._credentials
            if creds is None:
                creds_file = self._credentials_path or os.getenv(
                    "GOOGLE_APPLICATION_CREDENTIALS"
                )
                if creds_file and Path(creds_file).is_file():
                    creds = service_account.Credentials.from_service_account_file(
                        creds_file, scopes=_FIRESTORE_SCOPES
                    )
                else:
                    creds, _ = google.auth.default(scopes=_FIRESTORE_SCOPES)
                self._credentials = creds
            if not getattr(creds, "valid", False) or not getattr(creds, "token", None):
                creds.refresh(google.auth.transport.requests.Request())
            return {"Authorization": f"Bearer {creds.token}"}

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        try:
            headers = self._auth_headers()
            return self._session.request(
                method,
                url,
                headers=headers,
                json=json_body,
                params=params,
                timeout=self._timeout,
            )
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                f"Firestore {method} request failed: {exc}",
                service_name="GCP_Firestore",
            ) from exc

    def get_document(
        self,
        collection: str,
        doc_id: str,
    ) -> dict[str, Any] | None:
        """Fetches a single Firestore document or returns None on 404."""
        url = f"{self._base_url}/{collection}/{doc_id}"
        resp = self._request("GET", url)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            body_preview = (getattr(resp, "text", "") or "")[:200]
            raise ExternalServiceError(
                f"Firestore get on {collection}/{doc_id} failed ({resp.status_code}): {body_preview}",
                service_name="GCP_Firestore",
            )
        return decode_document(resp.json())

    def upsert_document(
        self,
        collection: str,
        doc_id: str,
        data: Mapping[str, Any],
    ) -> None:
        """Creates or replaces a Firestore document in the given collection."""
        url = f"{self._base_url}/{collection}/{doc_id}"
        resp = self._request(
            "PATCH",
            url,
            json_body={"fields": encode_document_fields(data)},
        )
        if resp.status_code >= 400:
            body_preview = (getattr(resp, "text", "") or "")[:200]
            raise ExternalServiceError(
                f"Firestore upsert on {collection}/{doc_id} failed ({resp.status_code}): {body_preview}",
                service_name="GCP_Firestore",
            )

    def delete_document(self, collection: str, doc_id: str) -> None:
        """Deletes a Firestore document, ignoring missing (404) documents."""
        url = f"{self._base_url}/{collection}/{doc_id}"
        resp = self._request("DELETE", url)
        if resp.status_code >= 400 and resp.status_code != 404:
            body_preview = (getattr(resp, "text", "") or "")[:200]
            raise ExternalServiceError(
                f"Firestore delete on {collection}/{doc_id} failed ({resp.status_code}): {body_preview}",
                service_name="GCP_Firestore",
            )

    def list_documents(
        self,
        collection: str,
        page_size: int = 300,
    ) -> list[dict[str, Any]]:
        """Lists all documents in a Firestore collection using pagination."""
        url = f"{self._base_url}/{collection}"
        docs: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {"pageSize": page_size}
            if page_token:
                params["pageToken"] = page_token
            resp = self._request("GET", url, params=params)
            if resp.status_code == 404:
                break
            if resp.status_code >= 400:
                body_preview = (getattr(resp, "text", "") or "")[:200]
                raise ExternalServiceError(
                    f"Firestore list on {collection} failed ({resp.status_code}): {body_preview}",
                    service_name="GCP_Firestore",
                )
            payload = resp.json()
            docs.extend(
                decode_document(raw_doc) for raw_doc in payload.get("documents") or []
            )
            page_token = payload.get("nextPageToken")
            if not page_token:
                break

        return docs

    def query_updated_since(
        self,
        collection: str,
        since_iso: str | None = None,
    ) -> list[dict[str, Any]]:
        """Queries documents whose updated_at field is strictly greater than since_iso."""
        if not since_iso:
            return self.list_documents(collection)

        url = f"{self._base_url}:runQuery"
        body = {
            "structuredQuery": {
                "from": [{"collectionId": collection}],
                "where": {
                    "fieldFilter": {
                        "field": {"fieldPath": "updated_at"},
                        "op": "GREATER_THAN",
                        "value": {"stringValue": since_iso},
                    }
                },
            }
        }
        resp = self._request("POST", url, json_body=body)
        if resp.status_code == 404:
            return []
        if resp.status_code >= 400:
            body_preview = (getattr(resp, "text", "") or "")[:200]
            raise ExternalServiceError(
                f"Firestore query on {collection} failed ({resp.status_code}): {body_preview}",
                service_name="GCP_Firestore",
            )
        payload = resp.json()
        if not isinstance(payload, list):
            return []
        return [
            decode_document(entry["document"])
            for entry in payload
            if isinstance(entry, dict) and isinstance(entry.get("document"), dict)
        ]


__all__ = [
    "FirestoreRestClient",
    "decode_document",
    "decode_firestore_value",
    "encode_document_fields",
    "encode_firestore_value",
]

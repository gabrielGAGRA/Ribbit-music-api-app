"""iTunes Search API adapter implementing TrackPreviewPort."""

from http import HTTPStatus

import niquests

from app.application.ports.services.music_service import (
    TrackPreview,
    TrackPreviewPort,
)
from app.domain.exceptions import ExternalServiceError


class ITunesAdapter(TrackPreviewPort):
    """External adapter for iTunes preview search API."""

    def __init__(self, session: niquests.Session | None = None) -> None:
        self._session = session or niquests.Session()

    def find_preview(self, term: str) -> TrackPreview | None:
        """Finds track preview via iTunes Search API.

        Raises:
            ExternalServiceError: If the external provider fails or times out.
        """
        try:
            params = {"term": term, "media": "music", "limit": "1"}
            res = self._session.get(
                "https://itunes.apple.com/search",
                params=params,
                timeout=5.0,
            )
            if res.status_code == HTTPStatus.OK:
                data = res.json()
                results = data.get("results", [])
                if results:
                    first = results[0]
                    return TrackPreview(
                        external_id=str(first.get("trackId")),
                        title=first.get("trackName"),
                        artist=first.get("artistName"),
                        preview_url=first.get("previewUrl"),
                        cover_url=first.get("artworkUrl100"),
                    )
                return None
            raise ExternalServiceError(
                f"iTunes API returned unexpected status {res.status_code}",
                service_name="iTunes",
                details={"status_code": res.status_code, "term": term},
            )
        except niquests.RequestException as exc:
            raise ExternalServiceError(
                f"Failed to communicate with iTunes search API: {exc}",
                service_name="iTunes",
                details={"term": term},
            ) from exc


__all__ = ["ITunesAdapter"]

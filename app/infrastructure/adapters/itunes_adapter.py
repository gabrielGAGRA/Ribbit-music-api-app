"""iTunes Search API adapter implementing TrackPreviewPort."""

from http import HTTPStatus

import niquests

from app.application.ports.services.music_service import (
    TrackPreview,
    TrackPreviewPort,
    normalize_match_text,
)
from app.domain.exceptions import ExternalServiceError


def _map_preview_item(item: dict[str, object]) -> TrackPreview:
    raw_year = str(item.get("releaseDate") or "")[:4]
    return TrackPreview(
        external_id=str(item.get("trackId")),
        title=str(item["trackName"]) if item.get("trackName") is not None else None,
        artist=str(item["artistName"]) if item.get("artistName") is not None else None,
        preview_url=(
            str(item["previewUrl"]) if item.get("previewUrl") is not None else None
        ),
        cover_url=(
            str(item["artworkUrl100"])
            if item.get("artworkUrl100") is not None
            else None
        ),
        genre=(
            str(item["primaryGenreName"])
            if item.get("primaryGenreName") is not None
            else None
        ),
        country=None,
        album=(
            str(item["collectionName"])
            if item.get("collectionName") is not None
            else None
        ),
        release_year=int(raw_year) if raw_year.isdigit() else None,
    )


def _select_best_preview(results: list[dict[str, object]], term: str) -> TrackPreview:
    norm_term = normalize_match_text(term)
    candidates = [_map_preview_item(item) for item in results]
    for candidate in candidates:
        c_title = normalize_match_text(candidate.title)
        c_artist = normalize_match_text(candidate.artist)
        if c_title and c_artist and c_title in norm_term and c_artist in norm_term:
            return candidate
    return candidates[0]


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
            params = {"term": term, "media": "music", "limit": "5"}
            res = self._session.get(
                "https://itunes.apple.com/search",
                params=params,
                timeout=5.0,
            )
            if res.status_code == HTTPStatus.OK:
                data = res.json()
                results = data.get("results", [])
                if results:
                    return _select_best_preview(results, term)
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

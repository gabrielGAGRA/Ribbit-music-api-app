"""Unit tests for ITunesAdapter preview search and exception translation."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import niquests
import pytest

from app.domain.exceptions import ExternalServiceError
from app.infrastructure.adapters.itunes_adapter import ITunesAdapter


def test_find_preview_returns_track_preview_on_success() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {
        "resultCount": 1,
        "results": [
            {
                "trackId": 1440806723,
                "trackName": "Bohemian Rhapsody",
                "artistName": "Queen",
                "previewUrl": "https://audio-ssl.itunes.apple.com/preview.m4a",
                "artworkUrl100": "https://is1-ssl.mzstatic.com/image/100x100bb.jpg",
            }
        ],
    }
    mock_session.get.return_value = mock_response

    adapter = ITunesAdapter(session=mock_session)
    preview = adapter.find_preview("Bohemian Rhapsody Queen")

    assert preview is not None
    assert preview.external_id == "1440806723"
    assert preview.title == "Bohemian Rhapsody"
    assert preview.artist == "Queen"
    assert preview.preview_url == "https://audio-ssl.itunes.apple.com/preview.m4a"
    assert preview.cover_url == "https://is1-ssl.mzstatic.com/image/100x100bb.jpg"
    mock_session.get.assert_called_once_with(
        "https://itunes.apple.com/search",
        params={"term": "Bohemian Rhapsody Queen", "media": "music", "limit": "1"},
        timeout=5.0,
    )


def test_find_preview_returns_none_when_results_empty() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {"resultCount": 0, "results": []}
    mock_session.get.return_value = mock_response

    adapter = ITunesAdapter(session=mock_session)
    preview = adapter.find_preview("NonExistentTrackXYZ")

    assert preview is None


def test_find_preview_raises_external_service_error_on_unexpected_status() -> None:
    mock_session = MagicMock(spec=niquests.Session)
    mock_response = MagicMock()
    mock_response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
    mock_session.get.return_value = mock_response

    adapter = ITunesAdapter(session=mock_session)

    with pytest.raises(ExternalServiceError) as exc_info:
        adapter.find_preview("Bohemian Rhapsody")

    assert "503" in str(exc_info.value)
    assert exc_info.value.details.get("service_name") == "iTunes"
    assert exc_info.value.details.get("status_code") == 503
    assert exc_info.value.details.get("term") == "Bohemian Rhapsody"


def test_find_preview_raises_external_service_error_on_network_failure() -> None:
    adapter = ITunesAdapter()

    with (
        patch(
            "niquests.Session.get",
            side_effect=niquests.RequestException("Connection timed out"),
        ),
        pytest.raises(ExternalServiceError) as exc_info,
    ):
        adapter.find_preview("Bohemian Rhapsody")

    assert "Connection timed out" in str(exc_info.value)
    assert exc_info.value.details.get("service_name") == "iTunes"
    assert exc_info.value.details.get("term") == "Bohemian Rhapsody"

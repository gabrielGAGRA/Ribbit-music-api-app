"""Spotify payload builders shared by adapter tests."""

from typing import Any

ALL_SCOPES = (
    "playlist-read-private playlist-read-collaborative playlist-modify-public "
    "playlist-modify-private user-read-playback-state user-read-currently-playing "
    "user-modify-playback-state ugc-image-upload"
)


def track_payload(track_id: str = "t1", name: str = "Song") -> dict[str, Any]:
    return {
        "id": track_id,
        "uri": f"spotify:track:{track_id}",
        "name": name,
        "duration_ms": 180_400,
        "preview_url": None,
        "artists": [{"name": "A"}, {"name": "B"}],
        "album": {
            "name": "Album",
            "release_date": "2019-05-03",
            "images": [{"url": "http://img/large"}, {"url": "http://img/small"}],
        },
    }

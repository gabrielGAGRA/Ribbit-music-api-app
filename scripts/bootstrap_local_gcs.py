"""Bootstrap script to ensure local GCS emulator has the initial bucket and Parquet file."""

import io
import logging
import os
import sys
import time

import pyarrow as pa
import pyarrow.parquet as pq
from google.cloud import storage

from app.config import load_settings

logger = logging.getLogger("scripts.bootstrap_local_gcs")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


def bootstrap_gcs_emulator() -> int:
    """Initializes the baseline Parquet catalog in local GCS emulator."""
    settings = load_settings()
    bucket_name = settings.gcs_bucket_name or "ribbit-catalog-local"
    tracks_file_path = settings.gcs_tracks_file_path or "Songs/songs_final.parquet"

    emulator_host = os.getenv("STORAGE_EMULATOR_HOST")
    if not emulator_host:
        logger.info("STORAGE_EMULATOR_HOST not set, skipping emulator bootstrap.")
        return 0

    logger.info("Connecting to GCS emulator at %s...", emulator_host)
    client = storage.Client()

    for attempt in range(15):
        try:
            bucket = client.bucket(bucket_name)
            if not bucket.exists():
                bucket = client.create_bucket(bucket_name)
                logger.info("Bucket '%s' created successfully.", bucket_name)
            else:
                logger.info("Bucket '%s' already exists.", bucket_name)

            blob = bucket.blob(tracks_file_path)
            if not blob.exists():
                logger.info("Initializing '%s' in bucket...", tracks_file_path)
                initial_data = {
                    "title": [
                        "Bohemian Rhapsody",
                        "Shape of You",
                        "Rap God",
                        "Blinding Lights",
                        "Smells Like Teen Spirit",
                    ],
                    "artist": [
                        "Queen",
                        "Ed Sheeran",
                        "Eminem",
                        "The Weeknd",
                        "Nirvana",
                    ],
                    "album": [
                        "A Night at the Opera",
                        "÷ (Divide)",
                        "The Marshall Mathers LP 2",
                        "After Hours",
                        "Nevermind",
                    ],
                    "duration_seconds": [354, 233, 363, 200, 301],
                    "genre": ["Rock", "Pop", "Hip Hop", "Pop", "Grunge"],
                    "country": [
                        "Reino Unido",
                        "Reino Unido",
                        "Estados Unidos",
                        "Canadá",
                        "Estados Unidos",
                    ],
                    "release_year": [1975, 2017, 2013, 2020, 1991],
                    "cover_url": [
                        "https://example.com/bohemian.jpg",
                        "https://example.com/shapeofyou.jpg",
                        "https://example.com/rapgod.jpg",
                        "https://example.com/blindinglights.jpg",
                        "https://example.com/nirvana.jpg",
                    ],
                    "itunes_preview_url": [
                        "https://example.com/bohemian_preview.mp3",
                        "https://example.com/shapeofyou_preview.mp3",
                        "https://example.com/rapgod_preview.mp3",
                        "https://example.com/blindinglights_preview.mp3",
                        "https://example.com/nirvana_preview.mp3",
                    ],
                    "spotify_id": [
                        "spotify:track:bohemian123",
                        "spotify:track:shapeofyou123",
                        "spotify:track:rapgod123",
                        "spotify:track:blinding123",
                        "spotify:track:nirvana123",
                    ],
                    "explicit": [False, False, True, False, False],
                }
                table = pa.Table.from_pydict(initial_data)
                sink = io.BytesIO()
                pq.write_table(table, sink)
                blob.upload_from_string(
                    sink.getvalue(),
                    content_type="application/octet-stream",
                )
                logger.info(
                    "Uploaded baseline catalog Parquet to '%s'.", tracks_file_path
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Attempt %d/15 failed: %s. Retrying in 1s...", attempt + 1, exc
            )
            time.sleep(1)
        else:
            return 0

    logger.error("Failed to bootstrap GCS emulator after 15 attempts.")
    return 1


if __name__ == "__main__":
    sys.exit(bootstrap_gcs_emulator())

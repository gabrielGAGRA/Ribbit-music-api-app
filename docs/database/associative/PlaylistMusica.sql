-- Ribbit Platform SQLite Database Architecture
-- Módulo: Associative / Associação Playlist e Músicas
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_track_id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
    added_at TEXT NOT NULL,
    CONSTRAINT uq_playlist_tracks_playlist_track UNIQUE (playlist_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_playlist_tracks_track_id ON playlist_tracks(track_id);

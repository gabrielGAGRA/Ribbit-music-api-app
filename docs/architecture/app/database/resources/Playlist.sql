-- Ribbit Platform SQLite Database Architecture
-- Módulo: Resources / Playlists e Capas Personalizadas
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS playlists (
    playlist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    spotify_playlist_id TEXT,
    is_exported INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    max_duration_seconds INTEGER,
    deck_filters TEXT,
    cover_image_url TEXT,
    source_playlist_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_playlists_user_id ON playlists(user_id);

CREATE TABLE IF NOT EXISTS playlist_images (
    playlist_id INTEGER PRIMARY KEY REFERENCES playlists(playlist_id) ON DELETE CASCADE,
    content_type TEXT NOT NULL,
    image_data BLOB NOT NULL,
    updated_at TEXT NOT NULL
);

-- Ribbit Platform SQLite Database Architecture
-- Módulo: Base / Músicas e Faixas do Catálogo
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS tracks (
    track_id INTEGER PRIMARY KEY AUTOINCREMENT,
    spotify_id TEXT,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT,
    duration_seconds INTEGER NOT NULL,
    genre TEXT NOT NULL,
    country TEXT,
    release_year INTEGER,
    cover_url TEXT,
    itunes_preview_url TEXT,
    explicit INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    CONSTRAINT ck_tracks_duration CHECK (duration_seconds > 0)
);

-- Índices para busca, filtros e ordenação rápida no catálogo
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre);

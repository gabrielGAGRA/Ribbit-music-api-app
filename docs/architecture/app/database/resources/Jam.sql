-- Ribbit Platform SQLite Database Architecture
-- Módulo: Resources / Sessões Jam, Participantes e Votação de Pulo
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS jams (
    jam_id INTEGER PRIMARY KEY AUTOINCREMENT,
    host_user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    room_name TEXT NOT NULL,
    room_code TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    current_track_id INTEGER REFERENCES tracks(track_id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    max_superlikes INTEGER NOT NULL DEFAULT 10,
    superlikes_used INTEGER NOT NULL DEFAULT 0,
    skip_votes_threshold INTEGER NOT NULL DEFAULT 3,
    accumulated_duration_seconds INTEGER NOT NULL DEFAULT 0,
    deck_source TEXT NOT NULL DEFAULT 'livre',
    source_playlist_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_jams_host_user_id ON jams(host_user_id);
CREATE INDEX IF NOT EXISTS idx_jams_current_track_id ON jams(current_track_id);

CREATE TABLE IF NOT EXISTS jam_participants (
    jam_id INTEGER NOT NULL REFERENCES jams(jam_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL,
    PRIMARY KEY (jam_id, user_id)
);

CREATE TABLE IF NOT EXISTS jam_skip_votes (
    jam_id INTEGER NOT NULL REFERENCES jams(jam_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    voted_at TEXT NOT NULL,
    PRIMARY KEY (jam_id, track_id, user_id)
);

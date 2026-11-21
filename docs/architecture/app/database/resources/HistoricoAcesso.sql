-- Ribbit Platform SQLite Database Architecture
-- Módulo: Resources / Histórico de Acessos a Faixas
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS track_accesses (
    access_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    accessed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_track_accesses_user_time ON track_accesses(user_id, accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_track_accesses_track_id ON track_accesses(track_id);
CREATE INDEX IF NOT EXISTS idx_track_accesses_user_track ON track_accesses(user_id, track_id);

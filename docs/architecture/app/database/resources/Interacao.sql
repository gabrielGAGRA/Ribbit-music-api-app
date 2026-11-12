-- Ribbit Platform SQLite Database Architecture
-- Módulo: Resources / Interações de Faixa (Curtidas, Superlikes, Rejeições)
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS interactions (
    interaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    created_at TEXT NOT NULL,
    source TEXT,
    jam_id INTEGER REFERENCES jams(jam_id) ON DELETE CASCADE,
    CONSTRAINT uq_interactions_user_track UNIQUE (user_id, track_id)
);

CREATE INDEX IF NOT EXISTS idx_interactions_user_id ON interactions(user_id);
CREATE INDEX IF NOT EXISTS idx_interactions_track_id ON interactions(track_id);

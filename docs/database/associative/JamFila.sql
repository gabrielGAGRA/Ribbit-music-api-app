-- Ribbit Platform SQLite Database Architecture
-- Módulo: Associative / Fila de Reprodução Colaborativa da Jam
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS jam_queue_items (
    jam_queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    jam_id INTEGER NOT NULL REFERENCES jams(jam_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
    vote_points INTEGER NOT NULL DEFAULT 0,
    added_at TEXT NOT NULL,
    CONSTRAINT uq_jam_queue_items_jam_track UNIQUE (jam_id, track_id)
);

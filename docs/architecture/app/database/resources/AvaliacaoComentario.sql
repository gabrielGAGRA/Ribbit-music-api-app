-- Ribbit Platform SQLite Database Architecture
-- Módulo: Resources / Avaliações de Músicas e Curtidas em Avaliações
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(track_id) ON DELETE CASCADE,
    rating INTEGER NOT NULL,
    text TEXT,
    likes_count INTEGER NOT NULL DEFAULT 0,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    CONSTRAINT ck_reviews_rating CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT ck_reviews_likes_count CHECK (likes_count >= 0)
);

CREATE INDEX IF NOT EXISTS idx_reviews_track_id ON reviews(track_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_reviews_active_user_track ON reviews(user_id, track_id) WHERE is_deleted = 0;

CREATE TABLE IF NOT EXISTS review_likes (
    review_id INTEGER NOT NULL REFERENCES reviews(review_id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (review_id, user_id)
);

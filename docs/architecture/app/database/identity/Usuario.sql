-- Ribbit Platform SQLite Database Architecture
-- Módulo: Identity / Contas de Usuários e Autenticação
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    spotify_id TEXT UNIQUE,
    display_name TEXT NOT NULL,
    age INTEGER NOT NULL,
    plan_id INTEGER NOT NULL REFERENCES plans(plan_id),
    primary_account_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    blocked_genres TEXT,
    favorite_genres TEXT,
    preferred_theme TEXT NOT NULL DEFAULT 'light',
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    birth_date TEXT,
    CONSTRAINT ck_users_age CHECK (age >= 0),
    CONSTRAINT ck_users_distinct_primary CHECK (primary_account_id IS NULL OR primary_account_id != user_id)
);

-- Índice para autenticação e pesquisa rápida por e-mail
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

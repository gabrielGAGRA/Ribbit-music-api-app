-- Ribbit Platform SQLite Database Architecture
-- Módulo: Base / Planos de Assinatura
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS plans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    monthly_price REAL NOT NULL,
    max_profiles INTEGER NOT NULL DEFAULT 1
);

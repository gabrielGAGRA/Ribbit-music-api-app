-- Ribbit Platform SQLite Database Architecture
-- Módulo: Base / Planos de Assinatura
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS plans (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    monthly_price REAL NOT NULL,
    max_profiles INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT ck_plans_price CHECK (monthly_price >= 0),
    CONSTRAINT ck_plans_max_profiles CHECK (max_profiles >= 1)
);

-- Ribbit Platform SQLite Database Architecture
-- Módulo: Base / Configurações de Custos Operacionais da Plataforma
-- Referência: app/infrastructure/repositories/schema.sql

CREATE TABLE IF NOT EXISTS platform_cost_settings (
    settings_id INTEGER PRIMARY KEY CHECK (settings_id = 1),
    content_cost_per_track REAL NOT NULL DEFAULT 0.04,
    infrastructure_fixed_cost REAL NOT NULL DEFAULT 10.00,
    infrastructure_cost_per_user REAL NOT NULL DEFAULT 0.50,
    updated_at TEXT NOT NULL
);

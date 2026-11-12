-- Ribbit Platform SQLite Database Architecture
-- Módulo: Base / Funções, Integridade, Triggers e Auditoria
-- Referência: app/infrastructure/repositories/schema.sql

-- 1. Habilitação de Chaves Estrangeiras (Foreign Keys)
-- No SQLite, a verificação de integridade referencial deve ser explicitamente habilitada por conexão:
PRAGMA foreign_keys = ON;

-- 2. Regras de Negócio e Stored Procedures no SQLite
-- Diferente de SGDBs cliente-servidor (como PostgreSQL), o SQLite não possui suporte nativo a PL/pgSQL
-- ou extensões procedurais arbitrárias (ex: pg_trgm).
-- No Ribbit, as regras complexas de negócio (como limite de perfis por plano familiar,
-- busca fonética/similaridade de músicas e sincronização com APIs do Spotify/GCS)
-- são implementadas na camada de aplicação e domínio (app/domain/ e app/application/use_cases/).

-- 3. Tabela de Auditoria do Sistema
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- 4. Exemplo de Triggers de Integridade e Auditoria em SQLite
-- Trigger para registrar exclusão lógica de músicas no log de auditoria:
CREATE TRIGGER IF NOT EXISTS trg_audit_track_soft_delete
AFTER UPDATE OF is_deleted ON tracks
WHEN NEW.is_deleted = 1 AND OLD.is_deleted = 0
BEGIN
    INSERT INTO audit_logs (event, status, created_at)
    VALUES ('track_soft_deleted: ' || NEW.track_id, 'SUCCESS', datetime('now'));
END;

-- Trigger para registrar encerramento de sala Jam no log de auditoria:
CREATE TRIGGER IF NOT EXISTS trg_audit_jam_deactivated
AFTER UPDATE OF is_active ON jams
WHEN NEW.is_active = 0 AND OLD.is_active = 1
BEGIN
    INSERT INTO audit_logs (event, status, created_at)
    VALUES ('jam_closed: ' || NEW.jam_id, 'SUCCESS', datetime('now'));
END;

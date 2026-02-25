-- Migration 004: Dashboard tables
-- Background tasks for task manager

CREATE TABLE IF NOT EXISTS background_tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    progress REAL DEFAULT 0.0,
    current_step TEXT DEFAULT '',
    parameters JSONB DEFAULT '{}'::jsonb,
    result JSONB,
    logs JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,

    CONSTRAINT background_tasks_status_check
        CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_background_tasks_user_status
    ON background_tasks(user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_background_tasks_active
    ON background_tasks(status) WHERE status IN ('queued', 'running');

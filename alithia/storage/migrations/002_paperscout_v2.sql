-- Migration 002: PaperScout v2 tables
-- Assessed papers and notification records for exactly-once email semantics

CREATE TABLE IF NOT EXISTS assessed_papers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    arxiv_id TEXT NOT NULL,
    query_categories TEXT NOT NULL,
    assessment_date DATE NOT NULL,
    paper_title TEXT,
    paper_authors JSONB DEFAULT '[]'::jsonb,
    paper_summary TEXT,
    pdf_url TEXT,
    relevance_score REAL,
    relevance_factors JSONB DEFAULT '{}'::jsonb,
    code_url TEXT,
    tldr TEXT,
    affiliations JSONB DEFAULT '[]'::jsonb,
    emailed BOOLEAN DEFAULT FALSE,
    assessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT assessed_papers_unique UNIQUE (user_id, arxiv_id, query_categories)
);

CREATE INDEX IF NOT EXISTS idx_assessed_papers_lookup
    ON assessed_papers(user_id, query_categories, assessment_date DESC);

CREATE TABLE IF NOT EXISTS notification_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    query_categories TEXT NOT NULL,
    notification_date DATE NOT NULL,
    paper_count INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    sent_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT notification_records_unique
        UNIQUE (user_id, query_categories, notification_date)
);

CREATE INDEX IF NOT EXISTS idx_notification_records_lookup
    ON notification_records(user_id, query_categories, notification_date);

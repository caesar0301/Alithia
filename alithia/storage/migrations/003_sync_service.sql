-- Migration 003: Sync service tables
-- Scholar profiles, publications, and sync log

CREATE TABLE IF NOT EXISTS scholar_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL UNIQUE,
    scholar_user_id TEXT NOT NULL,
    name TEXT,
    affiliation TEXT,
    interests JSONB DEFAULT '[]'::jsonb,
    h_index INTEGER,
    i10_index INTEGER,
    total_citations INTEGER DEFAULT 0,
    last_synced TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT scholar_profiles_user_unique UNIQUE (user_id)
);

CREATE TABLE IF NOT EXISTS scholar_publications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    scholar_article_id TEXT,
    title TEXT NOT NULL,
    authors JSONB DEFAULT '[]'::jsonb,
    year INTEGER,
    citation_count INTEGER DEFAULT 0,
    venue TEXT,
    url TEXT,
    last_synced TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT scholar_publications_unique UNIQUE (user_id, title, year)
);

CREATE INDEX IF NOT EXISTS idx_scholar_pub_user
    ON scholar_publications(user_id, citation_count DESC);

CREATE TABLE IF NOT EXISTS sync_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    connector_name TEXT NOT NULL,
    status TEXT NOT NULL,
    items_synced INTEGER DEFAULT 0,
    items_total INTEGER DEFAULT 0,
    sync_version TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,

    CONSTRAINT sync_log_recent UNIQUE (user_id, connector_name, started_at)
);

CREATE INDEX IF NOT EXISTS idx_sync_log_lookup
    ON sync_log(user_id, connector_name, started_at DESC);

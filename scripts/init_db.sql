-- Enable required extensions
-- Note: pgvector will be added in Week 3 for vector search
-- CREATE EXTENSION IF NOT EXISTS vector;
LOAD 'age';
SET search_path = ag_catalog, public;

-- Create RagGraph graph
SELECT create_graph('rag_knowledge');

-- Create structured_kb table
CREATE TABLE IF NOT EXISTS structured_kb (
    id TEXT PRIMARY KEY,
    type TEXT CHECK (type IN ('root_cause_analysis', 'cli_command_reference', 'escalation_resolution', 'configuration_parameter')),
    version INT DEFAULT 1,
    data JSONB NOT NULL,
    chunk_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT
);

-- Create human_overrides table
CREATE TABLE IF NOT EXISTS human_overrides (
    id SERIAL PRIMARY KEY,
    topic_hash TEXT,
    correction JSONB,
    status TEXT CHECK (status IN ('pending', 'active', 'reconciled', 'expired')),
    vote_count INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expiry TIMESTAMPTZ,
    created_by TEXT
);

-- Create document_metadata table
CREATE TABLE IF NOT EXISTS document_metadata (
    doc_id TEXT PRIMARY KEY,
    source_type TEXT,
    filename TEXT,
    page_count INT,
    chunk_count INT,
    minio_path TEXT,
    version INT DEFAULT 1,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create config table
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value JSONB,
    updated TIMESTAMPTZ DEFAULT NOW()
);

-- Create user_feedback table
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    query_id TEXT,
    rating TEXT CHECK (rating IN ('up', 'down')),
    correction TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- GIN indexes on structured_kb for tags, symptoms (JSONB fields)
CREATE INDEX IF NOT EXISTS idx_structured_kb_tags ON structured_kb USING GIN ((data->'tags'));
CREATE INDEX IF NOT EXISTS idx_structured_kb_symptoms ON structured_kb USING GIN ((data->'symptoms'));

-- B-tree index on type (text field - cannot use GIN)
CREATE INDEX IF NOT EXISTS idx_structured_kb_type ON structured_kb (type);

-- Partial index on human_overrides for active overrides
CREATE INDEX IF NOT EXISTS idx_human_overrides_active ON human_overrides (topic_hash, status, expiry) WHERE status = 'active';


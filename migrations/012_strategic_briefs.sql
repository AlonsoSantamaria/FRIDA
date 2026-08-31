CREATE TABLE IF NOT EXISTS strategic_briefs (
    brief_id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL REFERENCES city_assignments(assignment_id),
    brief_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    evidence_ids_json JSONB NOT NULL,
    foresight_json JSONB NOT NULL,
    brief_json JSONB NOT NULL,
    runtime_meta_json JSONB NOT NULL,
    historical_as_of TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS strategic_briefs_assignment_created_idx ON strategic_briefs(assignment_id, created_at DESC);

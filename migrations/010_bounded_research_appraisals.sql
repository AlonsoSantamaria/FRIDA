CREATE TABLE IF NOT EXISTS bounded_research_appraisals (
    research_id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL REFERENCES city_assignments(assignment_id),
    created_at TIMESTAMPTZ NOT NULL,
    input_fingerprint_sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    bundle_json JSONB NOT NULL,
    result_json JSONB,
    runtime_meta_json JSONB NOT NULL,
    UNIQUE(assignment_id, input_fingerprint_sha256)
);

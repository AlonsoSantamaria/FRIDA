CREATE TABLE IF NOT EXISTS source_registry_entries (
    source_registry_id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL REFERENCES city_assignments(assignment_id),
    discovered_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,
    proposal_fingerprint_sha256 TEXT NOT NULL,
    proposal_json JSONB NOT NULL,
    UNIQUE(assignment_id, proposal_fingerprint_sha256)
);
CREATE TABLE IF NOT EXISTS source_registry_events (
    event_id BIGSERIAL PRIMARY KEY,
    source_registry_id TEXT NOT NULL REFERENCES source_registry_entries(source_registry_id),
    occurred_at TIMESTAMPTZ NOT NULL,
    lifecycle_state TEXT NOT NULL,
    reason TEXT NOT NULL
);

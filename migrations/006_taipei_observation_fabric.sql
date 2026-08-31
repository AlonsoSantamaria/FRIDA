-- Append-only privacy-minimised observations, separate from canonical Signals.
CREATE TABLE IF NOT EXISTS source_fabric_observations (
    source_observation_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    source_timestamp TEXT,
    source_url TEXT NOT NULL,
    state_fingerprint_sha256 TEXT NOT NULL,
    classification TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    canonical_state_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS source_fabric_observations_source_idx
    ON source_fabric_observations(source_id, retrieved_at);

CREATE TABLE IF NOT EXISTS temporal_pattern_assessments (
    pattern_assessment_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    state TEXT NOT NULL,
    source_ids_json TEXT NOT NULL,
    observation_ids_json TEXT NOT NULL,
    rule_version TEXT NOT NULL
);

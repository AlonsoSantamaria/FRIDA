-- Canonical Attention/Candidate may be reused across replays; the bounded
-- specialist plan is immutable and belongs to one execution only.
CREATE TABLE IF NOT EXISTS execution_initial_plans (
    plan_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE REFERENCES case_execution_attempts(execution_id),
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

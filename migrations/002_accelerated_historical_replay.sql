-- FRIDA accelerated historical replay ledger.
-- This is intentionally separate from World Observations: every row records
-- governed historical evidence plus the later replay/execution time.
CREATE TABLE IF NOT EXISTS accelerated_replays (
    replay_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('RUNNING','PAUSED','COMPLETED','STOPPED')),
    authorization_reference TEXT NOT NULL,
    sequence_version TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS accelerated_replay_snapshots (
    replay_id TEXT NOT NULL REFERENCES accelerated_replays(replay_id),
    replay_sequence INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    source_date TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    evidence_class TEXT NOT NULL,
    inserted_at TEXT NOT NULL,
    state TEXT NOT NULL,
    signal_id TEXT,
    attention TEXT,
    candidate_signal_id TEXT,
    case_id TEXT,
    execution_id TEXT,
    PRIMARY KEY(replay_id, replay_sequence)
);
CREATE TABLE IF NOT EXISTS accelerated_replay_events (
    event_id BIGSERIAL PRIMARY KEY,
    replay_id TEXT NOT NULL REFERENCES accelerated_replays(replay_id),
    occurred_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS accelerated_replays_one_active_idx
    ON accelerated_replays(active) WHERE active = TRUE;
CREATE INDEX IF NOT EXISTS accelerated_replay_events_replay_idx
    ON accelerated_replay_events(replay_id, event_id);

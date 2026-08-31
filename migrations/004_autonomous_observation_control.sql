-- One durable, generic observation clock.  It owns operational state only;
-- source snapshots and governed intelligence remain separate.
CREATE TABLE IF NOT EXISTS observation_control (
    control_id INTEGER PRIMARY KEY CHECK (control_id = 1),
    state TEXT NOT NULL CHECK (state IN ('RUNNING','PAUSED','STOPPED')),
    cadence_seconds INTEGER NOT NULL,
    last_observation_at TEXT,
    next_observation_at TEXT,
    source_health TEXT NOT NULL,
    last_error_class TEXT,
    cycle_active BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS observation_control_events (
    event_id BIGSERIAL PRIMARY KEY,
    occurred_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
INSERT INTO observation_control (control_id,state,cadence_seconds,source_health,cycle_active,updated_at)
VALUES (1,'STOPPED',300,'NOT_STARTED',FALSE,now()::text)
ON CONFLICT (control_id) DO NOTHING;

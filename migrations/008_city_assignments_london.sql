-- Active-city projections are reversible.  Historical governed records remain
-- in place; assignment identifiers only control which operational history is
-- visible to the current city and scheduler.
CREATE TABLE IF NOT EXISTS city_assignments (
    assignment_id TEXT PRIMARY KEY,
    city_name TEXT NOT NULL,
    country_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE','INACTIVE','ARCHIVED')),
    created_at TEXT NOT NULL,
    activated_at TEXT,
    deactivated_at TEXT,
    metadata_json TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS city_assignments_one_active_idx
    ON city_assignments ((status = 'ACTIVE')) WHERE status = 'ACTIVE';

CREATE TABLE IF NOT EXISTS assignment_archives (
    archive_id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    schema_versions_json TEXT NOT NULL,
    object_counts_json TEXT NOT NULL,
    canonical_ids_json TEXT NOT NULL,
    table_hashes_json TEXT NOT NULL,
    restore_instructions TEXT NOT NULL,
    verified_at TEXT
);

CREATE TABLE IF NOT EXISTS observation_source_schedules (
    assignment_id TEXT NOT NULL REFERENCES city_assignments(assignment_id),
    source_id TEXT NOT NULL,
    cadence_seconds INTEGER NOT NULL,
    next_due_at TEXT,
    last_checked_at TEXT,
    source_health TEXT NOT NULL DEFAULT 'NOT_STARTED',
    last_error_class TEXT,
    PRIMARY KEY (assignment_id, source_id)
);

ALTER TABLE source_fabric_observations
    ADD COLUMN IF NOT EXISTS assignment_id TEXT NOT NULL DEFAULT 'TAIPEI_TECHNICAL_ARCHIVE';
ALTER TABLE observation_cycles
    ADD COLUMN IF NOT EXISTS assignment_id TEXT NOT NULL DEFAULT 'TAIPEI_TECHNICAL_ARCHIVE';
ALTER TABLE temporal_pattern_assessments
    ADD COLUMN IF NOT EXISTS assignment_id TEXT NOT NULL DEFAULT 'TAIPEI_TECHNICAL_ARCHIVE';

CREATE INDEX IF NOT EXISTS source_fabric_observations_assignment_idx
    ON source_fabric_observations(assignment_id, source_id, retrieved_at);
CREATE INDEX IF NOT EXISTS observation_cycles_assignment_idx
    ON observation_cycles(assignment_id, started_at);

INSERT INTO city_assignments (assignment_id,city_name,country_name,status,created_at,metadata_json)
VALUES ('QUERETARO_HISTORICAL_ARCHIVE','Querétaro','Mexico','ARCHIVED',now()::text,'{"mode":"historical-archive"}')
ON CONFLICT (assignment_id) DO NOTHING;
INSERT INTO city_assignments (assignment_id,city_name,country_name,status,created_at,metadata_json)
VALUES ('TAIPEI_TECHNICAL_ARCHIVE','Taipei','Taiwan','INACTIVE',now()::text,'{"mode":"technical-assignment"}')
ON CONFLICT (assignment_id) DO NOTHING;

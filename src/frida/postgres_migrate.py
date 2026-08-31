"""Tracked schema migration and explicit canonical-data import for Cloud SQL."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Iterable


def _migration_path(name: str) -> Path:
    """Find tracked SQL both from a source checkout and the deployed image."""
    candidates = (Path(__file__).parents[2] / "migrations" / name, Path("/app/migrations") / name, Path.cwd() / "migrations" / name)
    return next((candidate for candidate in candidates if candidate.is_file()), candidates[0])

MIGRATIONS = (
    ("001_frida_postgres", _migration_path("001_frida_postgres.sql")),
    ("002_accelerated_historical_replay", _migration_path("002_accelerated_historical_replay.sql")),
    ("003_execution_scoped_initial_plans", _migration_path("003_execution_scoped_initial_plans.sql")),
    ("004_autonomous_observation_control", _migration_path("004_autonomous_observation_control.sql")),
    ("005_operator_access_links", _migration_path("005_operator_access_links.sql")),
    ("006_taipei_observation_fabric", _migration_path("006_taipei_observation_fabric.sql")),
    ("007_temporal_pattern_memory", _migration_path("007_temporal_pattern_memory.sql")),
    ("008_city_assignments_london", _migration_path("008_city_assignments_london.sql")),
    ("009_first_appraisals", _migration_path("009_first_appraisals.sql")),
    ("010_bounded_research_appraisals", _migration_path("010_bounded_research_appraisals.sql")),
    ("011_source_registry", _migration_path("011_source_registry.sql")),
    ("012_strategic_briefs", _migration_path("012_strategic_briefs.sql")),
)
WP01_EXECUTION = "exec-controlled-replay-93a6c7ecb69741c69c18b4bea8c2c1d2"
FORESIGHT_EXECUTION = "foresight-verify-6505a6655a8645068fb14e4f9ce6435e"
SOURCE_STATE = "foresight-source-state-wr-2201-v1-2026-08-25"


def _connect(url: str):
    import psycopg
    return psycopg.connect(url)


def apply_schema(url: str) -> None:
    connection = _connect(url)
    cursor = connection.cursor()
    try:
        for version, migration in MIGRATIONS:
            cursor.execute(migration.read_text(encoding="utf-8"))
            cursor.execute("INSERT INTO schema_migrations(version) VALUES (%s) ON CONFLICT DO NOTHING", (version,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _rows(db: sqlite3.Connection, statement: str, values: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    return list(db.execute(statement, values).fetchall())


def _insert(cursor, table: str, columns: tuple[str, ...], rows: Iterable[tuple[object, ...]]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    placeholders = ",".join(["%s"] * len(columns))
    cursor.executemany(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING", rows)
    return len(rows)


def import_london_intelligence(url: str, london_path: Path) -> dict[str, int]:
    """Idempotently seed only validated London intelligence artifacts.

    The packaged seed contains sanitized structured artifacts and provenance,
    never credentials, model reasoning, or an execution database clone.
    """
    if not london_path.is_file():
        return {}
    london = sqlite3.connect(london_path)
    try:
        pg = _connect(url)
        cursor = pg.cursor()
        try:
            counts = {
                "london_source_fabric_observations": _insert(cursor, "source_fabric_observations", ("source_observation_id","source_id","retrieved_at","source_timestamp","source_url","state_fingerprint_sha256","classification","provenance_json","canonical_state_json","assignment_id"), _rows(london, "SELECT source_observation_id,source_id,retrieved_at,source_timestamp,source_url,state_fingerprint_sha256,classification,provenance_json,canonical_state_json,assignment_id FROM source_fabric_observations WHERE assignment_id='LONDON_FINAL_ACTIVE'")),
                "london_first_appraisals": _insert(cursor, "first_appraisals", ("appraisal_id","assignment_id","created_at","input_fingerprint_sha256","status","bundle_json","result_json","runtime_meta_json"), _rows(london, "SELECT * FROM first_appraisals WHERE assignment_id='LONDON_FINAL_ACTIVE'")),
                "london_bounded_research": _insert(cursor, "bounded_research_appraisals", ("research_id","assignment_id","created_at","input_fingerprint_sha256","status","bundle_json","result_json","runtime_meta_json"), _rows(london, "SELECT * FROM bounded_research_appraisals WHERE assignment_id='LONDON_FINAL_ACTIVE'")),
                "london_strategic_briefs": _insert(cursor, "strategic_briefs", ("brief_id","assignment_id","brief_type","created_at","status","evidence_ids_json","foresight_json","brief_json","runtime_meta_json","historical_as_of"), _rows(london, "SELECT * FROM strategic_briefs WHERE assignment_id='LONDON_FINAL_ACTIVE'")),
            }
            pg.commit()
            return counts
        finally:
            cursor.close(); pg.close()
    finally:
        london.close()


def import_canonical(url: str, wp01_path: Path, foresight_path: Path, manifest_path: Path, london_path: Path | None = None) -> dict[str, object]:
    """Import only the two approved Case/Execution histories, never dev residue."""
    wp = sqlite3.connect(wp01_path)
    fo = sqlite3.connect(foresight_path)
    counts: dict[str, int] = {}
    try:
        pg = _connect(url)
        cursor = pg.cursor()
        try:
            counts["observations"] = _insert(cursor, "observations", ("source_id","content_hash","source_reference","source_date","observed_at","evidence_class","replay_sequence"), _rows(wp, "SELECT * FROM observations WHERE source_id='DENUE'"))
            counts["candidate_signals"] = _insert(cursor, "candidate_signals", ("signal_id","source_id","observed_hash","observed_date","deduplication_key","provenance_reference","replay_sequence","triage_state"), _rows(wp, "SELECT * FROM candidate_signals WHERE signal_id='signal-cb43c4e133eb3f1f'"))
            counts["execution_attempts"] = _insert(cursor, "execution_attempts", ("execution_id","created_at","execution_mode","source_observation_mode","source_id","source_hash","candidate_signal_id","evidence_hashes_json","scenario_contract_version","authorization_reference","original_execution_reference"), _rows(wp, "SELECT * FROM execution_attempts WHERE execution_id=?", (WP01_EXECUTION,)))
            counts["execution_events"] = _insert(cursor, "execution_events", ("execution_id","occurred_at","event_type","payload_json"), _rows(wp, "SELECT execution_id,occurred_at,event_type,payload_json FROM execution_events WHERE execution_id=? ORDER BY event_id", (WP01_EXECUTION,)))
            counts["observation_cycles"] = _insert(cursor, "observation_cycles", ("cycle_id","started_at","completed_at","status","source_count","candidate_count","semantic_call_count"), _rows(wp, "SELECT * FROM observation_cycles"))
            counts["observation_cycle_events"] = _insert(cursor, "observation_cycle_events", ("cycle_id","occurred_at","event_type","message","payload_json"), _rows(wp, "SELECT cycle_id,occurred_at,event_type,message,payload_json FROM observation_cycle_events ORDER BY event_id"))
            counts["foresight_source_states"] = _insert(cursor, "foresight_source_states", ("source_state_id","created_at","bundle_id","contract_version","integrity_verified","geography","geographic_confidence","temporal_reference","payload_json"), _rows(fo, "SELECT * FROM foresight_source_states WHERE source_state_id=?", (SOURCE_STATE,)))
            input_rows = _rows(fo, "SELECT * FROM foresight_scenario_input_sets WHERE source_state_id=?", (SOURCE_STATE,))
            counts["foresight_scenario_input_sets"] = _insert(cursor, "foresight_scenario_input_sets", ("scenario_input_set_id","source_state_id","created_at","eligibility_status","payload_json","decision_json"), input_rows)
            counts["foresight_executions"] = _insert(cursor, "foresight_executions", ("foresight_execution_id","created_at","source_state_id","scenario_input_set_id","authorization_reference","status"), _rows(fo, "SELECT * FROM foresight_executions WHERE foresight_execution_id=?", (FORESIGHT_EXECUTION,)))
            counts["foresight_execution_events"] = _insert(cursor, "foresight_execution_events", ("foresight_execution_id","occurred_at","event_type","payload_json"), _rows(fo, "SELECT foresight_execution_id,occurred_at,event_type,payload_json FROM foresight_execution_events WHERE foresight_execution_id=? ORDER BY event_id", (FORESIGHT_EXECUTION,)))
            if london_path and london_path.is_file():
                # Keep the canonical import manifest together, while the
                # same idempotent seed is also safe at Cloud Run startup.
                counts.update(import_london_intelligence(url, london_path))
            pg.commit()
        finally:
            cursor.close()
            pg.close()
    finally:
        wp.close(); fo.close()
    manifest = {"schema": "001_frida_postgres", "wp01_execution": WP01_EXECUTION, "foresight_execution": FORESIGHT_EXECUTION,
                "source_state": SOURCE_STATE, "counts": counts,
                "sources": {str(wp01_path): hashlib.sha256(wp01_path.read_bytes()).hexdigest(), str(foresight_path): hashlib.sha256(foresight_path.read_bytes()).hexdigest(), **({str(london_path): hashlib.sha256(london_path.read_bytes()).hexdigest()} if london_path and london_path.is_file() else {})}}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("schema", "import-canonical"))
    parser.add_argument("--database-url", default=os.environ.get("FRIDA_DATABASE_URL"))
    parser.add_argument("--wp01", type=Path, default=Path("data/frida-golden-path.sqlite3"))
    parser.add_argument("--foresight", type=Path, default=Path("data/frida-foresight.sqlite3"))
    parser.add_argument("--manifest", type=Path, default=Path("data/cloud-migration-manifest.json"))
    parser.add_argument("--london-intelligence", type=Path)
    args = parser.parse_args()
    if not args.database_url: raise SystemExit("FRIDA_DATABASE_URL is required")
    if args.command == "schema": apply_schema(args.database_url)
    else: print(json.dumps(import_canonical(args.database_url, args.wp01, args.foresight, args.manifest, args.london_intelligence), indent=2))


if __name__ == "__main__": main()

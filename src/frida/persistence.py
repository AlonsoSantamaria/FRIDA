"""Durable staging storage for deterministic FRIDA behavior.

This module intentionally persists facts and audit events only.  It contains no
semantic-triage substitute and no model output.
"""
from __future__ import annotations

import sqlite3
import json
import hashlib
from datetime import datetime
from datetime import timedelta, timezone
from pathlib import Path
from threading import RLock

from .observation import CandidateSignal, ObservationAuditEvent, ReplaySnapshot
from .london_observation import CADENCES as LONDON_SOURCE_CADENCES


class StagingStore:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._lock = RLock()
        self.connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def _migrate(self) -> None:
        with self._lock:
            self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS observations (
                source_id TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                source_reference TEXT NOT NULL,
                source_date TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                evidence_class TEXT NOT NULL,
                replay_sequence INTEGER NOT NULL,
                PRIMARY KEY (source_id, content_hash)
            );
            CREATE TABLE IF NOT EXISTS candidate_signals (
                signal_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                observed_hash TEXT NOT NULL,
                observed_date TEXT NOT NULL,
                deduplication_key TEXT NOT NULL UNIQUE,
                provenance_reference TEXT NOT NULL,
                replay_sequence INTEGER NOT NULL,
                triage_state TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                detail TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS golden_path_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                state TEXT NOT NULL,
                view_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS execution_attempts (
                execution_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                execution_mode TEXT NOT NULL CHECK(execution_mode IN ('CONTROLLED_REPLAY_DEMO')),
                source_observation_mode TEXT NOT NULL CHECK(source_observation_mode IN ('HISTORICAL_REAL')),
                source_id TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                candidate_signal_id TEXT NOT NULL,
                evidence_hashes_json TEXT NOT NULL,
                scenario_contract_version TEXT NOT NULL,
                authorization_reference TEXT NOT NULL,
                original_execution_reference TEXT NOT NULL,
                FOREIGN KEY(candidate_signal_id) REFERENCES candidate_signals(signal_id)
            );
            CREATE TABLE IF NOT EXISTS execution_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(execution_id) REFERENCES execution_attempts(execution_id)
            );
            CREATE TABLE IF NOT EXISTS foresight_source_states (
                source_state_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                bundle_id TEXT NOT NULL UNIQUE,
                contract_version TEXT NOT NULL,
                integrity_verified INTEGER NOT NULL CHECK(integrity_verified IN (0, 1)),
                geography TEXT NOT NULL,
                geographic_confidence TEXT NOT NULL,
                temporal_reference TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS foresight_scenario_input_sets (
                scenario_input_set_id TEXT PRIMARY KEY,
                source_state_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                eligibility_status TEXT NOT NULL CHECK(eligibility_status IN ('ELIGIBLE', 'NOT_ELIGIBLE')),
                payload_json TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                FOREIGN KEY(source_state_id) REFERENCES foresight_source_states(source_state_id)
            );
            CREATE TABLE IF NOT EXISTS foresight_execution_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                foresight_execution_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS foresight_executions (
                foresight_execution_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                source_state_id TEXT NOT NULL,
                scenario_input_set_id TEXT NOT NULL,
                authorization_reference TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observation_cycles (
                cycle_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                source_count INTEGER NOT NULL,
                candidate_count INTEGER NOT NULL DEFAULT 0,
                semantic_call_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS observation_cycle_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(cycle_id) REFERENCES observation_cycles(cycle_id)
            );
            CREATE TABLE IF NOT EXISTS observation_control (
                control_id INTEGER PRIMARY KEY CHECK(control_id=1),
                state TEXT NOT NULL CHECK(state IN ('RUNNING','PAUSED','STOPPED')),
                cadence_seconds INTEGER NOT NULL,
                last_observation_at TEXT,
                next_observation_at TEXT,
                source_health TEXT NOT NULL,
                last_error_class TEXT,
                cycle_active INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observation_control_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS operator_access_links (
                code_digest TEXT PRIMARY KEY,
                expires_at TEXT NOT NULL,
                consumed_at TEXT
            );
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
            CREATE INDEX IF NOT EXISTS source_fabric_observations_source_idx ON source_fabric_observations(source_id,retrieved_at);
            CREATE TABLE IF NOT EXISTS temporal_pattern_assessments (
                pattern_assessment_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                state TEXT NOT NULL,
                source_ids_json TEXT NOT NULL,
                observation_ids_json TEXT NOT NULL,
                rule_version TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS first_appraisals (
                appraisal_id TEXT PRIMARY KEY,
                assignment_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                input_fingerprint_sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                bundle_json TEXT NOT NULL,
                result_json TEXT,
                runtime_meta_json TEXT NOT NULL,
                UNIQUE(assignment_id, input_fingerprint_sha256)
            );
            CREATE INDEX IF NOT EXISTS first_appraisals_assignment_created_idx ON first_appraisals(assignment_id, created_at);
            CREATE TABLE IF NOT EXISTS bounded_research_appraisals (
                research_id TEXT PRIMARY KEY,
                assignment_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                input_fingerprint_sha256 TEXT NOT NULL,
                status TEXT NOT NULL,
                bundle_json TEXT NOT NULL,
                result_json TEXT,
                runtime_meta_json TEXT NOT NULL,
                UNIQUE(assignment_id, input_fingerprint_sha256)
            );
            CREATE TABLE IF NOT EXISTS source_registry_entries (
                source_registry_id TEXT PRIMARY KEY,
                assignment_id TEXT NOT NULL,
                discovered_at TEXT NOT NULL,
                status TEXT NOT NULL,
                proposal_fingerprint_sha256 TEXT NOT NULL,
                proposal_json TEXT NOT NULL,
                UNIQUE(assignment_id, proposal_fingerprint_sha256)
            );
            CREATE TABLE IF NOT EXISTS source_registry_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_registry_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                lifecycle_state TEXT NOT NULL,
                reason TEXT NOT NULL,
                FOREIGN KEY(source_registry_id) REFERENCES source_registry_entries(source_registry_id)
            );
            CREATE TABLE IF NOT EXISTS strategic_briefs (
                brief_id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL, brief_type TEXT NOT NULL,
                created_at TEXT NOT NULL, status TEXT NOT NULL, evidence_ids_json TEXT NOT NULL,
                foresight_json TEXT NOT NULL, brief_json TEXT NOT NULL, runtime_meta_json TEXT NOT NULL,
                historical_as_of TEXT
            );
            CREATE TABLE IF NOT EXISTS city_assignments (
                assignment_id TEXT PRIMARY KEY,
                city_name TEXT NOT NULL,
                country_name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                activated_at TEXT,
                deactivated_at TEXT,
                metadata_json TEXT NOT NULL
            );
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
                assignment_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                cadence_seconds INTEGER NOT NULL,
                next_due_at TEXT,
                last_checked_at TEXT,
                source_health TEXT NOT NULL DEFAULT 'NOT_STARTED',
                last_error_class TEXT,
                PRIMARY KEY (assignment_id, source_id)
            );
            CREATE TABLE IF NOT EXISTS signals (
                signal_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                source_hash TEXT NOT NULL,
                source_reference TEXT NOT NULL,
                source_date TEXT NOT NULL,
                evidence_class TEXT NOT NULL,
                eligibility TEXT NOT NULL CHECK(eligibility IN ('IGNORE', 'WATCH', 'ATTENTION_PENDING')),
                created_at TEXT NOT NULL,
                UNIQUE(source_id, source_hash)
            );
            CREATE TABLE IF NOT EXISTS attention_assessments (
                attention_id TEXT PRIMARY KEY,
                signal_id TEXT NOT NULL UNIQUE,
                decision TEXT NOT NULL CHECK(decision IN ('IGNORE', 'WATCH', 'INVESTIGATE')),
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(signal_id) REFERENCES signals(signal_id)
            );
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                case_mode TEXT NOT NULL,
                title TEXT NOT NULL,
                label TEXT NOT NULL,
                source_observation_mode TEXT NOT NULL,
                status TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS case_links (
                case_id TEXT NOT NULL,
                link_type TEXT NOT NULL,
                link_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(case_id, link_type, link_id),
                FOREIGN KEY(case_id) REFERENCES cases(case_id)
            );
            CREATE TABLE IF NOT EXISTS execution_initial_plans (
                plan_id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(execution_id) REFERENCES case_execution_attempts(execution_id)
            );
            CREATE TABLE IF NOT EXISTS governed_evidence_bundles (
                bundle_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                integrity_verified INTEGER NOT NULL CHECK(integrity_verified IN (0, 1)),
                payload_json TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id)
            );
            CREATE TABLE IF NOT EXISTS case_execution_attempts (
                execution_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                candidate_signal_id TEXT NOT NULL,
                bundle_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                execution_mode TEXT NOT NULL,
                source_observation_mode TEXT NOT NULL,
                authorization_reference TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(case_id),
                FOREIGN KEY(candidate_signal_id) REFERENCES candidate_signals(signal_id),
                FOREIGN KEY(bundle_id) REFERENCES governed_evidence_bundles(bundle_id)
            );
            CREATE TABLE IF NOT EXISTS case_execution_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                execution_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(execution_id) REFERENCES case_execution_attempts(execution_id)
            );
            CREATE TABLE IF NOT EXISTS accelerated_replays (
                replay_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                authorization_reference TEXT NOT NULL,
                sequence_version TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS accelerated_replay_snapshots (
                replay_id TEXT NOT NULL,
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
                PRIMARY KEY(replay_id,replay_sequence),
                FOREIGN KEY(replay_id) REFERENCES accelerated_replays(replay_id)
            );
            CREATE TABLE IF NOT EXISTS accelerated_replay_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                replay_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(replay_id) REFERENCES accelerated_replays(replay_id)
            );
            """
            )
            for statement in (
                "ALTER TABLE source_fabric_observations ADD COLUMN assignment_id TEXT NOT NULL DEFAULT 'TAIPEI_TECHNICAL_ARCHIVE'",
                "ALTER TABLE observation_cycles ADD COLUMN assignment_id TEXT NOT NULL DEFAULT 'TAIPEI_TECHNICAL_ARCHIVE'",
                "ALTER TABLE temporal_pattern_assessments ADD COLUMN assignment_id TEXT NOT NULL DEFAULT 'TAIPEI_TECHNICAL_ARCHIVE'",
            ):
                try:
                    self.connection.execute(statement)
                except sqlite3.OperationalError:
                    pass
            self.connection.execute("INSERT OR IGNORE INTO city_assignments VALUES ('QUERETARO_HISTORICAL_ARCHIVE','Querétaro','Mexico','ARCHIVED',?,?,?,?)", (datetime.now().astimezone().isoformat(), None, None, '{\"mode\":\"historical-archive\"}'))
            self.connection.execute("INSERT OR IGNORE INTO city_assignments VALUES ('TAIPEI_TECHNICAL_ARCHIVE','Taipei','Taiwan','INACTIVE',?,?,?,?)", (datetime.now().astimezone().isoformat(), None, None, '{\"mode\":\"technical-assignment\"}'))
            self.connection.execute("""INSERT OR IGNORE INTO observation_control
                (control_id,state,cadence_seconds,source_health,cycle_active,updated_at)
                VALUES (1,'STOPPED',300,'NOT_STARTED',0,?)""", (datetime.now().astimezone().isoformat(),))
            self.connection.commit()

    def retained_snapshots(self) -> tuple[ReplaySnapshot, ...]:
        """Read approved observed source identities without claiming a new observation."""
        with self._lock:
            rows = self.connection.execute(
                "SELECT * FROM observations ORDER BY source_id, replay_sequence"
            ).fetchall()
        from .domain import EvidenceClass
        return tuple(ReplaySnapshot(
            source_id=row["source_id"], source_reference=row["source_reference"],
            source_date=datetime.fromisoformat(row["source_date"]), content_hash=row["content_hash"],
            evidence_class=EvidenceClass(row["evidence_class"]), replay_sequence=row["replay_sequence"],
            observed_at=datetime.now().astimezone(),
        ) for row in rows)

    def active_assignment(self) -> dict[str, object] | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM city_assignments WHERE status='ACTIVE' LIMIT 1").fetchone()
        return dict(row) if row else None

    def _archive_payload(self, assignment_id: str) -> tuple[dict[str, int], dict[str, str], dict[str, list[str]]]:
        scoped = {
            "source_fabric_observations": ("SELECT * FROM source_fabric_observations WHERE assignment_id=? ORDER BY source_observation_id", (assignment_id,)),
            "observation_cycles": ("SELECT * FROM observation_cycles WHERE assignment_id=? ORDER BY cycle_id", (assignment_id,)),
            "temporal_pattern_assessments": ("SELECT * FROM temporal_pattern_assessments WHERE assignment_id=? ORDER BY pattern_assessment_id", (assignment_id,)),
        }
        if assignment_id == "QUERETARO_HISTORICAL_ARCHIVE":
            scoped.update({
                "observations": ("SELECT * FROM observations ORDER BY source_id,content_hash", ()),
                "candidate_signals": ("SELECT * FROM candidate_signals ORDER BY signal_id", ()),
                "cases": ("SELECT * FROM cases ORDER BY case_id", ()),
                "execution_attempts": ("SELECT * FROM execution_attempts ORDER BY execution_id", ()),
                "case_execution_attempts": ("SELECT * FROM case_execution_attempts ORDER BY execution_id", ()),
                "foresight_executions": ("SELECT * FROM foresight_executions ORDER BY foresight_execution_id", ()),
                "accelerated_replays": ("SELECT * FROM accelerated_replays ORDER BY replay_id", ()),
            })
        counts: dict[str,int]={}; hashes: dict[str,str]={}; ids: dict[str,list[str]]={}
        for table,(statement,values) in scoped.items():
            rows=[dict(row) for row in self.connection.execute(statement,values).fetchall()]
            counts[table]=len(rows)
            hashes[table]=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
            key=next((candidate for candidate in ("source_observation_id","cycle_id","pattern_assessment_id","signal_id","case_id","execution_id","foresight_execution_id","replay_id","content_hash") if rows and candidate in rows[0]), None)
            ids[table]=[str(row[key]) for row in rows] if key else []
        return counts,hashes,ids

    def create_assignment_archive(self, archive_id: str, assignment_id: str) -> dict[str, object]:
        counts,hashes,ids=self._archive_payload(assignment_id)
        with self._lock, self.connection:
            versions=[str(row[0]) for row in self.connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
            self.connection.execute("INSERT INTO assignment_archives VALUES (?,?,?,?,?,?,?,?,?)", (archive_id,assignment_id,datetime.now(tz=timezone.utc).isoformat(),json.dumps(versions),json.dumps(counts,sort_keys=True),json.dumps(ids,sort_keys=True),json.dumps(hashes,sort_keys=True),"Restore by selecting archived assignment records and validating the recorded SHA-256 table hashes before reactivating a projection.",None))
        return {"archive_id":archive_id,"assignment_id":assignment_id,"object_counts":counts,"table_hashes":hashes}

    def verify_assignment_archive(self, archive_id: str) -> bool:
        with self._lock, self.connection:
            row=self.connection.execute("SELECT assignment_id,object_counts_json,table_hashes_json FROM assignment_archives WHERE archive_id=?",(archive_id,)).fetchone()
            if row is None: return False
            counts,hashes,_=self._archive_payload(str(row['assignment_id']))
            valid=counts==json.loads(row['object_counts_json']) and hashes==json.loads(row['table_hashes_json'])
            if valid: self.connection.execute("UPDATE assignment_archives SET verified_at=? WHERE archive_id=?",(datetime.now(tz=timezone.utc).isoformat(),archive_id))
        return valid

    def activate_london_assignment(self) -> dict[str, object]:
        """Switch only the active projection; historical rows are untouched."""
        from .city_assignment import LONDON, LONDON_ASSIGNMENT_ID
        now = datetime.now(tz=timezone.utc).isoformat()
        with self._lock, self.connection:
            self.connection.execute("UPDATE city_assignments SET status='INACTIVE',deactivated_at=? WHERE status='ACTIVE'", (now,))
            self.connection.execute("INSERT OR IGNORE INTO city_assignments VALUES (?,?,?,?,?,?,?,?)", (LONDON_ASSIGNMENT_ID,LONDON.city_name,LONDON.country_name,'INACTIVE',now,None,None,json.dumps({'mode':'live-final-assignment'},sort_keys=True)))
            self.connection.execute("UPDATE city_assignments SET status='ACTIVE',activated_at=?,deactivated_at=NULL WHERE assignment_id=?", (now,LONDON_ASSIGNMENT_ID))
            for source_id,cadence in LONDON_SOURCE_CADENCES.items():
                self.connection.execute("INSERT OR REPLACE INTO observation_source_schedules (assignment_id,source_id,cadence_seconds,next_due_at,last_checked_at,source_health,last_error_class) VALUES (?,?,?,?,?,?,?)", (LONDON_ASSIGNMENT_ID,source_id,cadence,now,None,'NOT_STARTED',None))
            self.connection.execute("UPDATE observation_control SET state='STOPPED',next_observation_at=NULL,cycle_active=0,source_health='NOT_STARTED',last_error_class=NULL,updated_at=? WHERE control_id=1", (now,))
            self._append_observation_control_event("assignment.activated", {"assignment_id": LONDON_ASSIGNMENT_ID})
        return self.active_assignment() or {}

    def due_observation_sources(self, assignment_id: str, now: datetime) -> list[str]:
        with self._lock:
            rows = self.connection.execute("SELECT source_id FROM observation_source_schedules WHERE assignment_id=? AND (next_due_at IS NULL OR next_due_at<=?) ORDER BY source_id", (assignment_id,now.isoformat())).fetchall()
        return [str(row['source_id']) for row in rows]

    def complete_observation_source(self, assignment_id: str, source_id: str, error_class: str | None) -> None:
        now=datetime.now(tz=timezone.utc)
        with self._lock, self.connection:
            row=self.connection.execute("SELECT cadence_seconds FROM observation_source_schedules WHERE assignment_id=? AND source_id=?", (assignment_id,source_id)).fetchone()
            if row is None: return
            next_due=(now+timedelta(seconds=int(row['cadence_seconds']))).isoformat()
            health='ERROR' if error_class else 'HEALTHY'
            self.connection.execute("UPDATE observation_source_schedules SET last_checked_at=?,next_due_at=?,source_health=?,last_error_class=? WHERE assignment_id=? AND source_id=?", (now.isoformat(),next_due,health,error_class,assignment_id,source_id))

    def create_observation_cycle(self, cycle_id: str, started_at: datetime, source_count: int, assignment_id: str | None = None) -> None:
        assignment_id = assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT INTO observation_cycles (cycle_id,started_at,status,source_count,assignment_id) VALUES (?, ?, 'RUNNING', ?, ?)",
                (cycle_id, started_at.isoformat(), source_count, assignment_id),
            )

    def append_observation_cycle_event(self, cycle_id: str, occurred_at: datetime, event_type: str, message: str, payload: dict[str, object]) -> None:
        with self._lock, self.connection:
            known = self.connection.execute("SELECT 1 FROM observation_cycles WHERE cycle_id=?", (cycle_id,)).fetchone()
            if known is None: raise ValueError("unknown observation cycle")
            self.connection.execute(
                "INSERT INTO observation_cycle_events (cycle_id,occurred_at,event_type,message,payload_json) VALUES (?, ?, ?, ?, ?)",
                (cycle_id, occurred_at.isoformat(), event_type, message, json.dumps(payload, sort_keys=True)),
            )

    def complete_observation_cycle(self, cycle_id: str, completed_at: datetime, status: str, candidate_count: int, semantic_call_count: int) -> None:
        with self._lock, self.connection:
            cursor = self.connection.execute(
                "UPDATE observation_cycles SET completed_at=?,status=?,candidate_count=?,semantic_call_count=? WHERE cycle_id=? AND status='RUNNING'",
                (completed_at.isoformat(), status, candidate_count, semantic_call_count, cycle_id),
            )
            if cursor.rowcount != 1: raise ValueError("observation cycle is immutable or unknown")

    def recent_observation_cycles(self, limit: int = 12, assignment_id: str | None = None) -> list[dict[str, object]]:
        assignment_id = assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        with self._lock:
            cycles = self.connection.execute(
                "SELECT * FROM observation_cycles WHERE assignment_id=? ORDER BY started_at DESC LIMIT ?", (assignment_id, limit)
            ).fetchall()
            output=[]
            for cycle in cycles:
                events=self.connection.execute(
                    "SELECT occurred_at,event_type,message,payload_json FROM observation_cycle_events WHERE cycle_id=? ORDER BY event_id", (cycle["cycle_id"],)
                ).fetchall()
                output.append({**dict(cycle), "events":[{**dict(event), "payload":json.loads(event["payload_json"])} for event in events]})
        return output

    def latest_source_fabric_observation(self, source_id: str, assignment_id: str | None = None) -> dict[str, object] | None:
        assignment_id = assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        with self._lock:
            row = self.connection.execute("SELECT * FROM source_fabric_observations WHERE source_id=? AND assignment_id=? ORDER BY retrieved_at DESC LIMIT 1", (source_id, assignment_id)).fetchone()
        return dict(row) if row else None

    def append_source_fabric_observation(self, snapshot: dict[str, object], classification: str, assignment_id: str | None = None) -> str:
        from uuid import uuid4
        if classification not in {"SAME_STATE", "ORDINARY_CHANGE", "POTENTIALLY_STRATEGIC_CHANGE"}:
            raise ValueError("invalid deterministic source classification")
        observation_id = "source-observation-" + uuid4().hex
        assignment_id = assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO source_fabric_observations (source_observation_id,source_id,retrieved_at,source_timestamp,source_url,state_fingerprint_sha256,classification,provenance_json,canonical_state_json,assignment_id) VALUES (?,?,?,?,?,?,?,?,?,?)", (
                observation_id, snapshot["source_id"], snapshot["retrieved_at"], snapshot.get("source_timestamp"), snapshot["source_url"], snapshot["fingerprint_sha256"], classification,
                json.dumps({key: snapshot[key] for key in ("source_id","authority","source_url","retrieved_at","source_timestamp","geography","adapter_version","normalization_version")}, sort_keys=True),
                json.dumps(snapshot["canonical_state"], sort_keys=True),
                assignment_id,
            ))
        return observation_id

    def recent_source_fabric_observations(self, source_id: str, limit: int = 12, assignment_id: str | None = None) -> list[dict[str, object]]:
        assignment_id = assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        with self._lock:
            rows = self.connection.execute("SELECT * FROM source_fabric_observations WHERE source_id=? AND assignment_id=? ORDER BY retrieved_at DESC LIMIT ?", (source_id, assignment_id, limit)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def recent_source_fabric_observations_all(self, limit: int = 24, assignment_id: str | None = None) -> list[dict[str, object]]:
        assignment_id = assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        with self._lock:
            rows = self.connection.execute("SELECT * FROM source_fabric_observations WHERE assignment_id=? ORDER BY retrieved_at DESC LIMIT ?", (assignment_id, limit)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def append_temporal_pattern_assessment(self, assessment: object, assignment_id: str | None = None) -> str:
        from uuid import uuid4
        assessment_id = "pattern-" + uuid4().hex
        assignment_id = assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO temporal_pattern_assessments (pattern_assessment_id,created_at,state,source_ids_json,observation_ids_json,rule_version,assignment_id) VALUES (?,?,?,?,?,?,?)", (
                assessment_id, datetime.now().astimezone().isoformat(), assessment.state,
                json.dumps(assessment.source_ids), json.dumps(assessment.observation_ids), assessment.rule_version,
                assignment_id,
            ))
        return assessment_id

    def first_appraisal_by_fingerprint(self, assignment_id: str, fingerprint: str) -> dict[str, object] | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM first_appraisals WHERE assignment_id=? AND input_fingerprint_sha256=?", (assignment_id, fingerprint)).fetchone()
        return dict(row) if row else None

    def first_appraisal_count_since(self, assignment_id: str, since: datetime) -> int:
        with self._lock:
            return int(self.connection.execute("SELECT COUNT(*) FROM first_appraisals WHERE assignment_id=? AND created_at>=?", (assignment_id, since.isoformat())).fetchone()[0])

    def append_first_appraisal(self, appraisal_id: str, assignment_id: str, bundle: dict[str, object], status: str, result: dict[str, object] | None, runtime_meta: dict[str, object]) -> None:
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO first_appraisals (appraisal_id,assignment_id,created_at,input_fingerprint_sha256,status,bundle_json,result_json,runtime_meta_json) VALUES (?,?,?,?,?,?,?,?)", (
                appraisal_id, assignment_id, datetime.now(tz=timezone.utc).isoformat(), str(bundle["input_fingerprint_sha256"]), status,
                json.dumps(bundle, sort_keys=True), json.dumps(result, sort_keys=True) if result is not None else None, json.dumps(runtime_meta, sort_keys=True),
            ))

    def append_bounded_research_appraisal(self, research_id: str, assignment_id: str, bundle: dict[str, object], status: str, result: dict[str, object] | None, runtime_meta: dict[str, object]) -> None:
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO bounded_research_appraisals (research_id,assignment_id,created_at,input_fingerprint_sha256,status,bundle_json,result_json,runtime_meta_json) VALUES (?,?,?,?,?,?,?,?)", (
                research_id, assignment_id, datetime.now(tz=timezone.utc).isoformat(), str(bundle["input_fingerprint_sha256"]), status,
                json.dumps(bundle, sort_keys=True), json.dumps(result, sort_keys=True) if result is not None else None, json.dumps(runtime_meta, sort_keys=True),
            ))

    def london_advisories(self, assignment_id: str = "LONDON_FINAL_ACTIVE") -> list[dict[str, object]]:
        with self._lock:
            rows = self.connection.execute(
                "SELECT appraisal_id AS record_id,created_at,result_json,bundle_json,'FIRST_APPRAISAL' AS kind FROM first_appraisals WHERE assignment_id=? AND status='VALIDATED' "
                "UNION ALL SELECT research_id AS record_id,created_at,result_json,bundle_json,'BOUNDED_RESEARCH' AS kind FROM bounded_research_appraisals WHERE assignment_id=? AND status='VALIDATED' ORDER BY created_at DESC",
                (assignment_id, assignment_id),
            ).fetchall()
        return [{**dict(row), "result": json.loads(str(row["result_json"])), "bundle": json.loads(str(row["bundle_json"]))} for row in rows]

    def append_strategic_brief(self, brief_id, assignment_id, brief_type, status, evidence_ids, foresight, brief, meta, historical_as_of=None):
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO strategic_briefs VALUES (?,?,?,?,?,?,?,?,?,?)", (brief_id,assignment_id,brief_type,datetime.now(tz=timezone.utc).isoformat(),status,json.dumps(evidence_ids),json.dumps(foresight),json.dumps(brief),json.dumps(meta),historical_as_of))

    def strategic_briefs(self, assignment_id="LONDON_FINAL_ACTIVE"):
        with self._lock: rows=self.connection.execute("SELECT * FROM strategic_briefs WHERE assignment_id=? AND status='VALIDATED' ORDER BY created_at DESC",(assignment_id,)).fetchall()
        result=[]; seen=set()
        for row in rows:
            key=(row["brief_type"],row["historical_as_of"])
            if key in seen: continue
            seen.add(key); result.append({**dict(row),"evidence_ids":json.loads(row["evidence_ids_json"]),"foresight":json.loads(row["foresight_json"]),"brief":json.loads(row["brief_json"]),"runtime_meta":json.loads(row["runtime_meta_json"])})
        return result

    def source_registry_by_fingerprint(self, assignment_id: str, fingerprint: str) -> dict[str, object] | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM source_registry_entries WHERE assignment_id=? AND proposal_fingerprint_sha256=?", (assignment_id, fingerprint)).fetchone()
        return dict(row) if row else None

    def create_source_registry_entry(self, source_registry_id: str, assignment_id: str, proposal: dict[str, object], fingerprint: str) -> None:
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO source_registry_entries (source_registry_id,assignment_id,discovered_at,status,proposal_fingerprint_sha256,proposal_json) VALUES (?,?,?,?,?,?)", (source_registry_id, assignment_id, datetime.now(tz=timezone.utc).isoformat(), "DISCOVERED", fingerprint, json.dumps(proposal, sort_keys=True)))
            self.connection.execute("INSERT INTO source_registry_events (source_registry_id,occurred_at,lifecycle_state,reason) VALUES (?,?,?,?)", (source_registry_id, datetime.now(tz=timezone.utc).isoformat(), "DISCOVERED", "FRIDA_AUTONOMOUS_SOURCE_DISCOVERY"))

    def set_source_registry_status(self, source_registry_id: str, status: str) -> None:
        if status not in {"SCREENED", "APPROVED", "SUSPENDED", "RETIRED"}: raise ValueError("invalid source lifecycle state")
        with self._lock, self.connection:
            self.connection.execute("UPDATE source_registry_entries SET status=? WHERE source_registry_id=?", (status, source_registry_id))

    def append_source_registry_event(self, source_registry_id: str, lifecycle_state: str, reason: str) -> None:
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO source_registry_events (source_registry_id,occurred_at,lifecycle_state,reason) VALUES (?,?,?,?)", (source_registry_id, datetime.now(tz=timezone.utc).isoformat(), lifecycle_state, reason))

    def source_discovery_count_since(self, assignment_id: str, since: datetime) -> int:
        with self._lock:
            return int(self.connection.execute("SELECT COUNT(*) FROM source_registry_entries WHERE assignment_id=? AND discovered_at>=?", (assignment_id, since.isoformat())).fetchone()[0])

    def create_operator_access_link(self, code_digest: str, expires_at: datetime) -> None:
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT INTO operator_access_links (code_digest,expires_at) VALUES (?,?)",
                (code_digest, expires_at.isoformat()),
            )

    def consume_operator_access_link(self, code_digest: str, now: datetime) -> bool:
        with self._lock, self.connection:
            cursor = self.connection.execute(
                """UPDATE operator_access_links SET consumed_at=?
                   WHERE code_digest=? AND consumed_at IS NULL AND expires_at>=?""",
                (now.isoformat(), code_digest, now.isoformat()),
            )
            return cursor.rowcount == 1

    def _append_observation_control_event(self, event_type: str, payload: dict[str, object]) -> None:
        self.connection.execute(
            "INSERT INTO observation_control_events (occurred_at,event_type,payload_json) VALUES (?, ?, ?)",
            (datetime.now().astimezone().isoformat(), event_type, json.dumps(payload, sort_keys=True)),
        )

    def observation_control(self) -> dict[str, object]:
        with self._lock:
            row = self.connection.execute("SELECT * FROM observation_control WHERE control_id=1").fetchone()
        if row is None: raise RuntimeError("observation control was not initialized")
        result = dict(row)
        result["cycle_active"] = bool(result["cycle_active"])
        result["heartbeat"] = "OBSERVING" if result["cycle_active"] else ("WAITING" if result["state"] == "RUNNING" else result["state"])
        return result

    def start_observation_control(self, cadence_seconds: int) -> dict[str, object]:
        from .observation_control import validate_cadence
        cadence = validate_cadence(cadence_seconds); now = datetime.now(tz=timezone.utc)
        with self._lock, self.connection:
            self.connection.execute("UPDATE observation_control SET state='RUNNING',cadence_seconds=?,next_observation_at=?,last_error_class=NULL,updated_at=? WHERE control_id=1", (cadence, now.isoformat(), now.isoformat()))
            self._append_observation_control_event("control.started", {"cadence_seconds": cadence})
        return self.observation_control()

    def pause_observation_control(self) -> dict[str, object]:
        now = datetime.now(tz=timezone.utc)
        with self._lock, self.connection:
            self.connection.execute("UPDATE observation_control SET state='PAUSED',updated_at=? WHERE control_id=1", (now.isoformat(),))
            self._append_observation_control_event("control.paused", {})
        return self.observation_control()

    def resume_observation_control(self) -> dict[str, object]:
        now = datetime.now(tz=timezone.utc)
        with self._lock, self.connection:
            self.connection.execute("UPDATE observation_control SET state='RUNNING',next_observation_at=?,last_error_class=NULL,updated_at=? WHERE control_id=1", (now.isoformat(), now.isoformat()))
            self._append_observation_control_event("control.resumed", {})
        return self.observation_control()

    def stop_observation_control(self) -> dict[str, object]:
        now = datetime.now(tz=timezone.utc)
        with self._lock, self.connection:
            self.connection.execute("UPDATE observation_control SET state='STOPPED',next_observation_at=NULL,updated_at=? WHERE control_id=1", (now.isoformat(),))
            self._append_observation_control_event("control.stopped", {})
        return self.observation_control()

    def set_observation_source_health(self, source_health: str) -> None:
        with self._lock, self.connection:
            current = self.connection.execute("SELECT source_health FROM observation_control WHERE control_id=1").fetchone()
            if current and current["source_health"] != source_health:
                self.connection.execute("UPDATE observation_control SET source_health=?,updated_at=? WHERE control_id=1", (source_health, datetime.now(tz=timezone.utc).isoformat()))
                self._append_observation_control_event("source.health", {"source_health": source_health})

    def claim_due_observation_cycle(self, now: datetime) -> bool:
        with self._lock, self.connection:
            cursor = self.connection.execute("""UPDATE observation_control SET cycle_active=1,updated_at=?
                WHERE control_id=1 AND state='RUNNING' AND cycle_active=0
                AND (next_observation_at IS NULL OR next_observation_at<=?)""", (now.isoformat(), now.isoformat()))
            if cursor.rowcount:
                self._append_observation_control_event("observation.claimed", {})
                return True
        return False

    def finish_observation_cycle_claim(self, now: datetime, *, source_health: str, outcome: dict[str, object] | None = None, error_class: str | None = None, pause: bool = False) -> None:
        with self._lock, self.connection:
            row = self.connection.execute("SELECT cadence_seconds FROM observation_control WHERE control_id=1").fetchone()
            if row is None: raise RuntimeError("observation control was not initialized")
            state = "PAUSED" if pause else "RUNNING"
            next_at = None if pause else (now + timedelta(seconds=int(row["cadence_seconds"]))).isoformat()
            self.connection.execute("UPDATE observation_control SET state=?,cycle_active=0,last_observation_at=?,next_observation_at=?,source_health=?,last_error_class=?,updated_at=? WHERE control_id=1", (state,now.isoformat(),next_at,source_health,error_class,now.isoformat()))
            event = "observation.failed" if pause else "observation.completed"
            self._append_observation_control_event(event, {"source_health": source_health, "error_class": error_class, "outcome": outcome or {}})

    def create_accelerated_replay(self, replay_id: str, authorization_reference: str, sequence_version: str) -> None:
        if not authorization_reference.strip(): raise ValueError("replay authorization is required")
        with self._lock, self.connection:
            active=self.connection.execute("SELECT replay_id FROM accelerated_replays WHERE active=1 LIMIT 1").fetchone()
            if active is not None: raise ValueError("accelerated historical replay already active: " + active["replay_id"])
            self.connection.execute("INSERT INTO accelerated_replays VALUES (?, ?, 'RUNNING', ?, ?, 1)",
                (replay_id, datetime.now().astimezone().isoformat(), authorization_reference, sequence_version))

    def append_accelerated_replay_event(self, replay_id: str, event_type: str, message: str, payload: dict[str, object]) -> None:
        with self._lock, self.connection:
            known=self.connection.execute("SELECT 1 FROM accelerated_replays WHERE replay_id=?",(replay_id,)).fetchone()
            if known is None: raise ValueError("unknown accelerated replay")
            self.connection.execute("INSERT INTO accelerated_replay_events (replay_id,occurred_at,event_type,message,payload_json) VALUES (?, ?, ?, ?, ?)",
                (replay_id,datetime.now().astimezone().isoformat(),event_type,message,json.dumps(payload,sort_keys=True)))

    def create_accelerated_replay_snapshot(self, replay_id: str, item, inserted_at: datetime) -> None:
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO accelerated_replay_snapshots (replay_id,replay_sequence,source_id,source_reference,source_date,content_hash,evidence_class,inserted_at,state) VALUES (?, ?, ?, ?, ?, ?, 'REAL', ?, 'INTRODUCED')",
                (replay_id,item.replay_sequence,item.source_id,item.source_reference,item.source_date.isoformat(),item.content_hash,inserted_at.isoformat()))

    def update_accelerated_replay_snapshot(self, replay_id: str, sequence: int, state: str, **links: str) -> None:
        allowed={"signal_id","attention","candidate_signal_id","case_id","execution_id"}
        if set(links).difference(allowed): raise ValueError("unsupported accelerated replay link")
        sets=["state=?"]; values=[state]
        for key,value in links.items(): sets.append(key+"=?"); values.append(value)
        values += [replay_id,sequence]
        with self._lock, self.connection:
            cursor=self.connection.execute("UPDATE accelerated_replay_snapshots SET " + ",".join(sets) + " WHERE replay_id=? AND replay_sequence=?",values)
            if cursor.rowcount != 1: raise ValueError("unknown accelerated replay snapshot")

    def accelerated_replay(self, replay_id: str | None = None) -> dict[str, object] | None:
        with self._lock:
            row=self.connection.execute("SELECT * FROM accelerated_replays " + ("WHERE replay_id=?" if replay_id else "ORDER BY created_at DESC LIMIT 1"), (replay_id,) if replay_id else ()).fetchone()
            if row is None: return None
            snapshots=self.connection.execute("SELECT * FROM accelerated_replay_snapshots WHERE replay_id=? ORDER BY replay_sequence",(row["replay_id"],)).fetchall()
            events=self.connection.execute("SELECT occurred_at,event_type,message,payload_json FROM accelerated_replay_events WHERE replay_id=? ORDER BY event_id",(row["replay_id"],)).fetchall()
        return {**dict(row),"snapshots":[dict(x) for x in snapshots],"events":[{**dict(x),"payload":json.loads(x["payload_json"])} for x in events]}

    def complete_accelerated_replay(self, replay_id: str, status: str) -> None:
        if status not in {"COMPLETED","STOPPED"}: raise ValueError("invalid accelerated replay terminal state")
        with self._lock, self.connection:
            cursor=self.connection.execute("UPDATE accelerated_replays SET status=?,active=0 WHERE replay_id=? AND active=1",(status,replay_id))
            if cursor.rowcount != 1: raise ValueError("accelerated replay is not active")

    def create_foresight_source_state(self, state: dict[str, object]) -> None:
        """Append a separately governed Foresight evidence state; never touches WP01."""
        required = {"source_state_id", "created_at", "bundle_id", "contract_version", "integrity_verified", "geography", "geographic_confidence", "temporal_reference", "sources", "facts"}
        if not required.issubset(state) or not state["integrity_verified"]:
            raise ValueError("foresight source state requires verified immutable evidence")
        with self._lock, self.connection:
            try:
                self.connection.execute(
                    """INSERT INTO foresight_source_states VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (str(state["source_state_id"]), str(state["created_at"]), str(state["bundle_id"]), str(state["contract_version"]), 1,
                     str(state["geography"]), str(state["geographic_confidence"]), str(state["temporal_reference"]), json.dumps(state, sort_keys=True)),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("foresight source state already exists; ledger is append-only") from error

    def create_foresight_scenario_input_set(self, input_set: dict[str, object], decision: dict[str, object]) -> None:
        """Persist an eligibility result before any future Foresight runtime exists."""
        required = {"scenario_input_set_id", "source_state_id", "horizon", "computation_mode", "scenario_definitions", "assumptions"}
        if not required.issubset(input_set) or decision.get("status") not in {"ELIGIBLE", "NOT_ELIGIBLE"}:
            raise ValueError("foresight scenario input set or eligibility decision is invalid")
        with self._lock, self.connection:
            known = self.connection.execute("SELECT 1 FROM foresight_source_states WHERE source_state_id=?", (str(input_set["source_state_id"]),)).fetchone()
            if known is None:
                raise ValueError("foresight scenario input set requires a persisted source state")
            try:
                self.connection.execute(
                    """INSERT INTO foresight_scenario_input_sets VALUES (?, ?, ?, ?, ?, ?)""",
                    (str(input_set["scenario_input_set_id"]), str(input_set["source_state_id"]), datetime.now().astimezone().isoformat(),
                     str(decision["status"]), json.dumps(input_set, sort_keys=True), json.dumps(decision, sort_keys=True)),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("foresight ScenarioInputSet already exists; ledger is append-only") from error

    def foresight_source_state(self, source_state_id: str) -> dict[str, object] | None:
        with self._lock:
            row = self.connection.execute("SELECT payload_json FROM foresight_source_states WHERE source_state_id=?", (source_state_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def append_foresight_event(self, execution_id: str, event_type: str, payload: dict[str, object]) -> None:
        """Append-only future Foresight audit; never stores model thoughts or raw prose."""
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT INTO foresight_execution_events (foresight_execution_id, occurred_at, event_type, payload_json) VALUES (?, ?, ?, ?)",
                (execution_id, datetime.now().astimezone().isoformat(), event_type, json.dumps(payload, sort_keys=True)),
            )

    def create_foresight_execution(self, execution_id: str, source_state_id: str, input_set_id: str, authorization_reference: str) -> None:
        with self._lock, self.connection:
            try:
                self.connection.execute("INSERT INTO foresight_executions VALUES (?, ?, ?, ?, ?, ?)", (execution_id, datetime.now().astimezone().isoformat(), source_state_id, input_set_id, authorization_reference, "STARTED"))
            except sqlite3.IntegrityError as error: raise ValueError("foresight execution identity already exists") from error

    def record_signal(self, snapshot: ReplaySnapshot, signal_id: str, eligibility: str) -> None:
        """Persist a source signal before FRIDA Attention; a signal is not a candidate."""
        if eligibility not in {"IGNORE", "WATCH", "ATTENTION_PENDING"}:
            raise ValueError("unsupported deterministic signal eligibility")
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (signal_id, snapshot.source_id, snapshot.content_hash, snapshot.source_reference,
                 snapshot.source_date.isoformat(), snapshot.evidence_class.value, eligibility,
                 snapshot.observed_at.isoformat()),
            )

    def record_attention(self, signal_id: str, decision: str, reason: str, attention_id: str) -> None:
        """Append the governed FRIDA Attention decision; only INVESTIGATE may create a candidate."""
        if decision not in {"IGNORE", "WATCH", "INVESTIGATE"} or not reason.strip():
            raise ValueError("invalid attention decision")
        with self._lock, self.connection:
            known = self.connection.execute("SELECT 1 FROM signals WHERE signal_id=?", (signal_id,)).fetchone()
            if known is None: raise ValueError("attention requires a persisted signal")
            self.connection.execute("INSERT INTO attention_assessments VALUES (?, ?, ?, ?, ?)",
                (attention_id, signal_id, decision, reason, datetime.now().astimezone().isoformat()))

    def signal(self, signal_id: str) -> dict[str, object] | None:
        with self._lock:
            row=self.connection.execute("SELECT * FROM signals WHERE signal_id=?", (signal_id,)).fetchone()
            return dict(row) if row else None

    def signal_for_source_hash(self, source_id: str, source_hash: str) -> dict[str, object] | None:
        with self._lock:
            row=self.connection.execute("SELECT * FROM signals WHERE source_id=? AND source_hash=?", (source_id, source_hash)).fetchone()
            return dict(row) if row else None

    def attention(self, signal_id: str) -> dict[str, object] | None:
        with self._lock:
            row=self.connection.execute("SELECT * FROM attention_assessments WHERE signal_id=?", (signal_id,)).fetchone()
        return dict(row) if row else None

    def candidate_for_deduplication_key(self, key: str):
        with self._lock:
            row=self.connection.execute("SELECT signal_id FROM candidate_signals WHERE deduplication_key=?", (key,)).fetchone()
        return self.candidate(str(row["signal_id"])) if row else None

    def create_case(self, case_id: str, *, title: str, label: str, case_mode: str,
                    source_observation_mode: str, metadata: dict[str, object]) -> None:
        if not all((case_id, title.strip(), label.strip(), case_mode, source_observation_mode)):
            raise ValueError("generic case identity is incomplete")
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (case_id, datetime.now().astimezone().isoformat(), case_mode, title, label,
                 source_observation_mode, "OPEN", json.dumps(metadata, sort_keys=True)))

    def link_case(self, case_id: str, link_type: str, link_id: str) -> None:
        if link_type not in {"SIGNAL", "CANDIDATE", "EXECUTION", "FORESIGHT_SOURCE_STATE", "FORESIGHT_EXECUTION"}:
            raise ValueError("unsupported generic case link")
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO case_links VALUES (?, ?, ?, ?)",
                (case_id, link_type, link_id, datetime.now().astimezone().isoformat()))

    def persist_evidence_bundle(self, bundle: dict[str, object]) -> None:
        required = {"bundle_id", "case_id", "evidence"}
        evidence = bundle.get("evidence", [])
        if not required.issubset(bundle) or not isinstance(evidence, list) or not evidence:
            raise ValueError("governed evidence bundle is incomplete")
        for item in evidence:
            if not isinstance(item, dict) or not {"evidence_id", "content_hash", "source_id", "source_reference", "limitations", "evidence_class"}.issubset(item):
                raise ValueError("governed evidence bundle has incomplete provenance")
            if len(str(item["content_hash"])) != 64 or item["evidence_class"] not in {"REAL", "DERIVED"}:
                raise ValueError("governed evidence bundle integrity or class is invalid")
        with self._lock, self.connection:
            try:
                self.connection.execute("INSERT INTO governed_evidence_bundles VALUES (?, ?, ?, ?, ?)",
                    (str(bundle["bundle_id"]), str(bundle["case_id"]), datetime.now().astimezone().isoformat(), 1,
                     json.dumps(bundle, sort_keys=True)))
            except sqlite3.IntegrityError as error:
                raise ValueError("governed evidence bundle already exists; history is append-only") from error

    def create_case_execution(self, execution: dict[str, object]) -> None:
        required = {"execution_id", "case_id", "candidate_signal_id", "bundle_id", "execution_mode", "source_observation_mode", "authorization_reference"}
        if not required.issubset(execution) or not str(execution["authorization_reference"]).strip():
            raise ValueError("generic case execution is incomplete")
        with self._lock, self.connection:
            candidate = self.connection.execute("SELECT 1 FROM candidate_signals WHERE signal_id=?", (str(execution["candidate_signal_id"]),)).fetchone()
            bundle = self.connection.execute("SELECT case_id FROM governed_evidence_bundles WHERE bundle_id=?", (str(execution["bundle_id"]),)).fetchone()
            if candidate is None or bundle is None or bundle["case_id"] != execution["case_id"]:
                raise ValueError("generic case execution linkage is invalid")
            self.connection.execute("INSERT INTO case_execution_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(execution["execution_id"]), str(execution["case_id"]), str(execution["candidate_signal_id"]), str(execution["bundle_id"]),
                 datetime.now().astimezone().isoformat(), str(execution["execution_mode"]), str(execution["source_observation_mode"]), str(execution["authorization_reference"])))
            self.link_case(str(execution["case_id"]), "EXECUTION", str(execution["execution_id"]))

    def persist_execution_initial_plan(self, execution_id: str, plan: dict[str, object]) -> None:
        with self._lock, self.connection:
            try:
                self.connection.execute("INSERT INTO execution_initial_plans VALUES (?, ?, ?, ?)",
                    ("plan-" + str(execution_id).split("-")[-1], execution_id, datetime.now().astimezone().isoformat(), json.dumps(plan, sort_keys=True)))
            except sqlite3.IntegrityError as error:
                raise ValueError("execution initial plan already exists; history is append-only") from error

    def case(self, case_id: str) -> dict[str, object] | None:
        with self._lock:
            row=self.connection.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
            links=self.connection.execute("SELECT link_type,link_id FROM case_links WHERE case_id=? ORDER BY created_at", (case_id,)).fetchall()
        if row is None: return None
        value=dict(row); value["metadata"]=json.loads(value.pop("metadata_json")); value["links"]=[dict(item) for item in links]; return value

    def cases(self) -> list[dict[str, object]]:
        with self._lock:
            rows=self.connection.execute("SELECT case_id FROM cases ORDER BY created_at DESC").fetchall()
        return [value for row in rows if (value:=self.case(row["case_id"])) is not None]

    def create_controlled_replay_execution(self, execution: dict[str, object]) -> None:
        """Append one governed execution identity; existing rows are never mutable."""
        required = {
            "execution_id", "created_at", "execution_mode", "source_observation_mode",
            "source_id", "source_hash", "candidate_signal_id", "evidence_hashes",
            "scenario_contract_version", "authorization_reference", "original_execution_reference",
        }
        if not required.issubset(execution):
            raise ValueError("controlled replay execution missing immutable fields")
        if execution["execution_mode"] != "CONTROLLED_REPLAY_DEMO":
            raise ValueError("only explicitly governed controlled replay executions are permitted")
        if execution["source_observation_mode"] != "HISTORICAL_REAL":
            raise ValueError("controlled replay must reference a historical real observation")
        with self._lock, self.connection:
            candidate = self.connection.execute(
                "SELECT source_id, observed_hash FROM candidate_signals WHERE signal_id=?",
                (str(execution["candidate_signal_id"]),),
            ).fetchone()
            if candidate is None:
                raise ValueError("controlled replay requires an existing immutable candidate")
            if candidate["source_id"] != execution["source_id"] or candidate["observed_hash"] != execution["source_hash"]:
                raise ValueError("controlled replay source/candidate provenance mismatch")
            try:
                self.connection.execute(
                    """INSERT INTO execution_attempts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(execution["execution_id"]), str(execution["created_at"]), str(execution["execution_mode"]),
                        str(execution["source_observation_mode"]), str(execution["source_id"]), str(execution["source_hash"]),
                        str(execution["candidate_signal_id"]), json.dumps(execution["evidence_hashes"], sort_keys=True),
                        str(execution["scenario_contract_version"]), str(execution["authorization_reference"]),
                        str(execution["original_execution_reference"]),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("execution identity already exists; ledger is append-only") from error

    def append_execution_event(self, execution_id: str, occurred_at: datetime, event_type: str, payload: dict[str, object]) -> None:
        """Execution progress is additive: terminal history is never overwritten."""
        with self._lock, self.connection:
            known = self.connection.execute("SELECT 1 FROM execution_attempts WHERE execution_id=?", (execution_id,)).fetchone()
            generic = False
            if known is None:
                known = self.connection.execute("SELECT 1 FROM case_execution_attempts WHERE execution_id=?", (execution_id,)).fetchone()
                generic = known is not None
            if known is None: raise ValueError("cannot append an event for an unknown execution")
            # A completed execution can receive a transparent audit correction,
            # but never a newly invented runtime failure. This protects the
            # ledger when console visibility is weaker than persisted evidence.
            if event_type == "execution.stopped_runtime_failure":
                completed = self.connection.execute(
                    ("SELECT 1 FROM case_execution_events" if generic else "SELECT 1 FROM execution_events") + " WHERE execution_id=? AND event_type='execution.completed' LIMIT 1",
                    (execution_id,),
                ).fetchone()
                if completed is not None:
                    raise ValueError("cannot append runtime failure after a completed execution")
            self.connection.execute(
                ("INSERT INTO case_execution_events" if generic else "INSERT INTO execution_events") + " (execution_id, occurred_at, event_type, payload_json) VALUES (?, ?, ?, ?)",
                (execution_id, occurred_at.isoformat(), event_type, json.dumps(payload, sort_keys=True)),
            )

    def execution_attempt(self, execution_id: str) -> dict[str, object] | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM execution_attempts WHERE execution_id=?", (execution_id,)).fetchone()
            generic = row is None
            if generic: row = self.connection.execute("SELECT * FROM case_execution_attempts WHERE execution_id=?", (execution_id,)).fetchone()
            table = "case_execution_events" if generic else "execution_events"
            events = self.connection.execute(f"SELECT occurred_at, event_type, payload_json FROM {table} WHERE execution_id=? ORDER BY event_id", (execution_id,)).fetchall()
        if row is None:
            return None
        result = dict(row)
        if generic:
            bundle=self.connection.execute("SELECT payload_json FROM governed_evidence_bundles WHERE bundle_id=?", (result["bundle_id"],)).fetchone()
            result["evidence_hashes"]={item["evidence_id"]:item["content_hash"] for item in json.loads(bundle[0])["evidence"]}
            result["generic_case_execution"] = True
            result["case"] = self.case(str(result["case_id"]))
        else:
            result["evidence_hashes"] = json.loads(result.pop("evidence_hashes_json"))
        result["events"] = [
            {"occurred_at": item["occurred_at"], "event_type": item["event_type"], "payload": json.loads(item["payload_json"])}
            for item in events
        ]
        return result

    def lead_execution_records(self) -> list[dict[str, object]]:
        """Read compatible historical and generic Lead runs; projections decide presentation."""
        with self._lock:
            legacy=self.connection.execute("SELECT execution_id FROM execution_attempts ORDER BY created_at DESC").fetchall()
            generic=self.connection.execute("SELECT execution_id FROM case_execution_attempts ORDER BY created_at DESC").fetchall()
        records=[self.execution_attempt(row["execution_id"]) for row in [*legacy, *generic]]
        return [record for record in records if record is not None]

    def save_golden_path_view(self, view: dict[str, object]) -> None:
        """Persist the read-only, provenance-safe presentation projection."""
        required = {"run_id", "state", "audit"}
        if not required.issubset(view):
            raise ValueError("golden path view missing required fields")
        created_at = view["audit"][0]["at"] if view["audit"] else datetime.now().astimezone().isoformat()
        with self._lock, self.connection:
            self.connection.execute(
                """INSERT INTO golden_path_runs VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET state=excluded.state, view_json=excluded.view_json""",
                (str(view["run_id"]), str(created_at), str(view["state"]), json.dumps(view, sort_keys=True)),
            )

    def latest_golden_path_view(self) -> dict[str, object] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT view_json FROM golden_path_runs ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return json.loads(row[0]) if row else None

    def reserve_observation(self, snapshot: ReplaySnapshot) -> bool:
        """Atomically reserve a source/hash pair; False means already observed."""
        try:
            with self._lock, self.connection:
                self.connection.execute("""INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?)""", (
                    snapshot.source_id, snapshot.content_hash, snapshot.source_reference,
                    snapshot.source_date.isoformat(), snapshot.observed_at.isoformat(),
                    snapshot.evidence_class.value, snapshot.replay_sequence,
                ))
            return True
        except sqlite3.IntegrityError:
            return False

    def record_candidate(self, signal: CandidateSignal) -> None:
        with self._lock, self.connection:
            self.connection.execute(
                """INSERT INTO candidate_signals VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    signal.signal_id, signal.source_id, signal.observed_hash,
                    signal.observed_date.isoformat(), signal.deduplication_key,
                    signal.provenance_reference, signal.replay_sequence,
                    "SEMANTIC_TRIAGE_PENDING",
                ),
            )

    def candidate(self, signal_id: str) -> CandidateSignal | None:
        """Return immutable candidate facts for a governed execution reference."""
        with self._lock:
            row = self.connection.execute(
                "SELECT signal_id, source_id, observed_hash, observed_date, deduplication_key, provenance_reference, replay_sequence "
                "FROM candidate_signals WHERE signal_id=?", (signal_id,)
            ).fetchone()
        if row is None:
            return None
        return CandidateSignal(
            row["signal_id"], row["source_id"], row["observed_hash"],
            datetime.fromisoformat(row["observed_date"]), row["deduplication_key"],
            row["provenance_reference"], row["replay_sequence"],
        )

    def record_audit(self, events: tuple[ObservationAuditEvent, ...]) -> None:
        occurred_at = datetime.now().astimezone().isoformat()
        with self._lock, self.connection:
            self.connection.executemany(
                "INSERT INTO audit_events (occurred_at, event_type, source_id, detail) VALUES (?, ?, ?, ?)",
                [(occurred_at, event.event_type, event.source_id, event.detail) for event in events],
            )

    def status(self) -> dict[str, object]:
        with self._lock:
            counts = {
                "observations": self.connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0],
                "candidate_signals": self.connection.execute("SELECT COUNT(*) FROM candidate_signals").fetchone()[0],
                "audit_events": self.connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0],
            }
        return {"service": "FRIDA technical staging", "semantic_triage": "PENDING_GOOGLE_GATE_4", **counts}

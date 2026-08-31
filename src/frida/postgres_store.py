"""Read-only PostgreSQL projection store used by Cloud Run.

The deployed judge surface reads immutable, already-governed artifacts.  It is
deliberately not an alternate observation/runtime implementation: mutation
continues to belong to the controlled local execution paths until separately
authorized.
"""
from __future__ import annotations

import json
import hashlib
from datetime import datetime
from datetime import timedelta, timezone
from contextlib import suppress
from typing import Any
from .london_observation import CADENCES as LONDON_SOURCE_CADENCES


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


class PostgresStore:
    """Small, explicit Cloud SQL read adapter for the FRIDA judge experience."""

    def __init__(self, database_url: str):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as error:  # pragma: no cover - deployment dependency
            raise RuntimeError("PostgreSQL support requires psycopg") from error
        self._psycopg = psycopg
        self.connection = psycopg.connect(database_url, row_factory=dict_row, autocommit=True)

    def close(self) -> None:
        self.connection.close()

    def _one(self, statement: str, values: tuple[object, ...] = ()) -> dict[str, Any] | None:
        with self.connection.cursor() as cursor:
            cursor.execute(statement, values)
            return cursor.fetchone()

    def _all(self, statement: str, values: tuple[object, ...] = ()) -> list[dict[str, Any]]:
        with self.connection.cursor() as cursor:
            cursor.execute(statement, values)
            return list(cursor.fetchall())

    def status(self) -> dict[str, object]:
        counts: dict[str, int] = {}
        for table in ("observations", "candidate_signals", "audit_events"):
            row = self._one(f"SELECT COUNT(*) AS count FROM {table}")
            counts[table] = int((row or {"count": 0})["count"])
        return {"service": "FRIDA Cloud Run judge surface", "semantic_triage": "GOVERNED_HISTORY", **counts}

    def latest_golden_path_view(self) -> dict[str, object] | None:
        row = self._one("SELECT view_json FROM golden_path_runs ORDER BY created_at DESC LIMIT 1")
        return _json(row["view_json"]) if row else None

    def active_assignment(self) -> dict[str, object] | None:
        return self._one("SELECT * FROM city_assignments WHERE status='ACTIVE' LIMIT 1")

    def source_registry_by_fingerprint(self, assignment_id: str, fingerprint: str):
        return self._one("SELECT * FROM source_registry_entries WHERE assignment_id=%s AND proposal_fingerprint_sha256=%s", (assignment_id, fingerprint))

    def create_source_registry_entry(self, source_registry_id, assignment_id, proposal, fingerprint):
        now=datetime.now(tz=timezone.utc).isoformat()
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO source_registry_entries (source_registry_id,assignment_id,discovered_at,status,proposal_fingerprint_sha256,proposal_json) VALUES (%s,%s,%s,%s,%s,%s)", (source_registry_id,assignment_id,now,'DISCOVERED',fingerprint,json.dumps(proposal,sort_keys=True)))
            cursor.execute("INSERT INTO source_registry_events (source_registry_id,occurred_at,lifecycle_state,reason) VALUES (%s,%s,%s,%s)", (source_registry_id,now,'DISCOVERED','FRIDA_AUTONOMOUS_SOURCE_DISCOVERY'))

    def set_source_registry_status(self, source_registry_id, status):
        with self.connection.cursor() as cursor: cursor.execute("UPDATE source_registry_entries SET status=%s WHERE source_registry_id=%s", (status,source_registry_id))

    def append_source_registry_event(self, source_registry_id, lifecycle_state, reason):
        with self.connection.cursor() as cursor: cursor.execute("INSERT INTO source_registry_events (source_registry_id,occurred_at,lifecycle_state,reason) VALUES (%s,%s,%s,%s)", (source_registry_id,datetime.now(tz=timezone.utc).isoformat(),lifecycle_state,reason))

    def source_discovery_count_since(self, assignment_id, since):
        row=self._one("SELECT COUNT(*) AS count FROM source_registry_entries WHERE assignment_id=%s AND discovered_at>=%s", (assignment_id,since.isoformat()))
        return int(row['count']) if row else 0

    def _archive_payload(self, assignment_id: str) -> tuple[dict[str, int], dict[str, str], dict[str, list[str]]]:
        scoped = {
            "source_fabric_observations": ("SELECT * FROM source_fabric_observations WHERE assignment_id=%s ORDER BY source_observation_id", (assignment_id,)),
            "observation_cycles": ("SELECT * FROM observation_cycles WHERE assignment_id=%s ORDER BY cycle_id", (assignment_id,)),
            "temporal_pattern_assessments": ("SELECT * FROM temporal_pattern_assessments WHERE assignment_id=%s ORDER BY pattern_assessment_id", (assignment_id,)),
        }
        if assignment_id == "QUERETARO_HISTORICAL_ARCHIVE":
            scoped.update({
                "observations": ("SELECT * FROM observations ORDER BY source_id,content_hash", ()), "candidate_signals": ("SELECT * FROM candidate_signals ORDER BY signal_id", ()),
                "cases": ("SELECT * FROM cases ORDER BY case_id", ()), "execution_attempts": ("SELECT * FROM execution_attempts ORDER BY execution_id", ()),
                "case_execution_attempts": ("SELECT * FROM case_execution_attempts ORDER BY execution_id", ()), "foresight_executions": ("SELECT * FROM foresight_executions ORDER BY foresight_execution_id", ()),
                "accelerated_replays": ("SELECT * FROM accelerated_replays ORDER BY replay_id", ()),
            })
        counts: dict[str,int]={}; hashes: dict[str,str]={}; ids: dict[str,list[str]]={}
        for table,(statement,values) in scoped.items():
            rows=self._all(statement,values); counts[table]=len(rows)
            hashes[table]=hashlib.sha256(json.dumps(rows,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
            key=next((candidate for candidate in ("source_observation_id","cycle_id","pattern_assessment_id","signal_id","case_id","execution_id","foresight_execution_id","replay_id","content_hash") if rows and candidate in rows[0]),None)
            ids[table]=[str(row[key]) for row in rows] if key else []
        return counts,hashes,ids

    def create_assignment_archive(self, archive_id: str, assignment_id: str) -> dict[str, object]:
        counts,hashes,ids=self._archive_payload(assignment_id)
        versions=[str(row['version']) for row in self._all("SELECT version FROM schema_migrations ORDER BY version")]
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO assignment_archives (archive_id,assignment_id,created_at,schema_versions_json,object_counts_json,canonical_ids_json,table_hashes_json,restore_instructions,verified_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NULL)", (archive_id,assignment_id,datetime.now(tz=timezone.utc).isoformat(),json.dumps(versions),json.dumps(counts,sort_keys=True),json.dumps(ids,sort_keys=True),json.dumps(hashes,sort_keys=True),"Restore by selecting archived assignment records and validating the recorded SHA-256 table hashes before reactivating a projection."))
        return {"archive_id":archive_id,"assignment_id":assignment_id,"object_counts":counts,"table_hashes":hashes}

    def verify_assignment_archive(self, archive_id: str) -> bool:
        row=self._one("SELECT assignment_id,object_counts_json,table_hashes_json FROM assignment_archives WHERE archive_id=%s",(archive_id,))
        if row is None: return False
        counts,hashes,_=self._archive_payload(str(row['assignment_id']))
        valid=counts==_json(row['object_counts_json']) and hashes==_json(row['table_hashes_json'])
        if valid:
            with self.connection.cursor() as cursor: cursor.execute("UPDATE assignment_archives SET verified_at=%s WHERE archive_id=%s",(datetime.now(tz=timezone.utc).isoformat(),archive_id))
        return valid

    def activate_london_assignment(self) -> dict[str, object]:
        from .city_assignment import LONDON, LONDON_ASSIGNMENT_ID
        now = datetime.now(tz=timezone.utc).isoformat()
        with self.connection.cursor() as cursor:
            cursor.execute("UPDATE city_assignments SET status='INACTIVE',deactivated_at=%s WHERE status='ACTIVE'", (now,))
            cursor.execute("INSERT INTO city_assignments (assignment_id,city_name,country_name,status,created_at,metadata_json) VALUES (%s,%s,%s,'INACTIVE',%s,%s) ON CONFLICT DO NOTHING", (LONDON_ASSIGNMENT_ID,LONDON.city_name,LONDON.country_name,now,json.dumps({'mode':'live-final-assignment'},sort_keys=True)))
            cursor.execute("UPDATE city_assignments SET status='ACTIVE',activated_at=%s,deactivated_at=NULL WHERE assignment_id=%s", (now,LONDON_ASSIGNMENT_ID))
            for source_id,cadence in LONDON_SOURCE_CADENCES.items():
                cursor.execute("INSERT INTO observation_source_schedules (assignment_id,source_id,cadence_seconds,next_due_at,last_checked_at,source_health,last_error_class) VALUES (%s,%s,%s,%s,NULL,'NOT_STARTED',NULL) ON CONFLICT (assignment_id,source_id) DO UPDATE SET cadence_seconds=EXCLUDED.cadence_seconds,next_due_at=EXCLUDED.next_due_at,source_health='NOT_STARTED',last_error_class=NULL", (LONDON_ASSIGNMENT_ID,source_id,cadence,now))
            cursor.execute("UPDATE observation_control SET state='STOPPED',next_observation_at=NULL,cycle_active=FALSE,source_health='NOT_STARTED',last_error_class=NULL,updated_at=%s WHERE control_id=1", (now,))
        self._append_observation_control_event("assignment.activated", {"assignment_id": LONDON_ASSIGNMENT_ID})
        return self.active_assignment() or {}

    def due_observation_sources(self, assignment_id: str, now: datetime) -> list[str]:
        rows=self._all("SELECT source_id FROM observation_source_schedules WHERE assignment_id=%s AND (next_due_at IS NULL OR next_due_at<=%s) ORDER BY source_id", (assignment_id,now.isoformat()))
        return [str(row['source_id']) for row in rows]

    def complete_observation_source(self, assignment_id: str, source_id: str, error_class: str | None) -> None:
        now=datetime.now(tz=timezone.utc)
        row=self._one("SELECT cadence_seconds FROM observation_source_schedules WHERE assignment_id=%s AND source_id=%s", (assignment_id,source_id))
        if row is None: return
        with self.connection.cursor() as cursor:
            cursor.execute("UPDATE observation_source_schedules SET last_checked_at=%s,next_due_at=%s,source_health=%s,last_error_class=%s WHERE assignment_id=%s AND source_id=%s", (now.isoformat(),(now+timedelta(seconds=int(row['cadence_seconds']))).isoformat(),'ERROR' if error_class else 'HEALTHY',error_class,assignment_id,source_id))

    def recent_observation_cycles(self, limit: int = 12, assignment_id: str | None = None) -> list[dict[str, object]]:
        assignment_id=assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        cycles = self._all("SELECT * FROM observation_cycles WHERE assignment_id=%s ORDER BY started_at DESC LIMIT %s", (assignment_id,limit))
        output: list[dict[str, object]] = []
        for cycle in cycles:
            events = self._all(
                "SELECT occurred_at,event_type,message,payload_json FROM observation_cycle_events WHERE cycle_id=%s ORDER BY event_id",
                (cycle["cycle_id"],),
            )
            output.append({**cycle, "events": [{**event, "payload": _json(event["payload_json"])} for event in events]})
        return output

    def create_observation_cycle(self, cycle_id: str, started_at: datetime, source_count: int, assignment_id: str | None = None) -> None:
        assignment_id=assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO observation_cycles (cycle_id,started_at,status,source_count,assignment_id) VALUES (%s,%s,'RUNNING',%s,%s)", (cycle_id, started_at.isoformat(), source_count,assignment_id))

    def append_observation_cycle_event(self, cycle_id: str, occurred_at: datetime, event_type: str, message: str, payload: dict[str, object]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO observation_cycle_events (cycle_id,occurred_at,event_type,message,payload_json) VALUES (%s,%s,%s,%s,%s)", (cycle_id, occurred_at.isoformat(), event_type, message, json.dumps(payload, sort_keys=True)))

    def complete_observation_cycle(self, cycle_id: str, completed_at: datetime, status: str, candidate_count: int, semantic_call_count: int) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("UPDATE observation_cycles SET completed_at=%s,status=%s,candidate_count=%s,semantic_call_count=%s WHERE cycle_id=%s AND status='RUNNING'", (completed_at.isoformat(), status, candidate_count, semantic_call_count, cycle_id))
            if cursor.rowcount != 1:
                raise ValueError("observation cycle is immutable or unknown")

    def latest_source_fabric_observation(self, source_id: str, assignment_id: str | None = None) -> dict[str, object] | None:
        assignment_id=assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        return self._one("SELECT * FROM source_fabric_observations WHERE source_id=%s AND assignment_id=%s ORDER BY retrieved_at DESC LIMIT 1", (source_id,assignment_id))

    def append_source_fabric_observation(self, snapshot: dict[str, object], classification: str, assignment_id: str | None = None) -> str:
        from uuid import uuid4
        if classification not in {"SAME_STATE", "ORDINARY_CHANGE", "POTENTIALLY_STRATEGIC_CHANGE"}:
            raise ValueError("invalid deterministic source classification")
        observation_id = "source-observation-" + uuid4().hex
        assignment_id=assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        provenance = {key: snapshot[key] for key in ("source_id","authority","source_url","retrieved_at","source_timestamp","geography","adapter_version","normalization_version")}
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO source_fabric_observations (source_observation_id,source_id,retrieved_at,source_timestamp,source_url,state_fingerprint_sha256,classification,provenance_json,canonical_state_json,assignment_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (observation_id,snapshot["source_id"],snapshot["retrieved_at"],snapshot.get("source_timestamp"),snapshot["source_url"],snapshot["fingerprint_sha256"],classification,json.dumps(provenance,sort_keys=True),json.dumps(snapshot["canonical_state"],sort_keys=True),assignment_id))
        return observation_id

    def recent_source_fabric_observations(self, source_id: str, limit: int = 12, assignment_id: str | None = None) -> list[dict[str, object]]:
        assignment_id=assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        return list(reversed(self._all("SELECT * FROM source_fabric_observations WHERE source_id=%s AND assignment_id=%s ORDER BY retrieved_at DESC LIMIT %s", (source_id,assignment_id,limit))))

    def recent_source_fabric_observations_all(self, limit: int = 24, assignment_id: str | None = None) -> list[dict[str, object]]:
        assignment_id=assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        return list(reversed(self._all("SELECT * FROM source_fabric_observations WHERE assignment_id=%s ORDER BY retrieved_at DESC LIMIT %s", (assignment_id,limit))))

    def append_temporal_pattern_assessment(self, assessment: object, assignment_id: str | None = None) -> str:
        from uuid import uuid4
        assessment_id = "pattern-" + uuid4().hex
        assignment_id=assignment_id or str((self.active_assignment() or {}).get('assignment_id') or 'TAIPEI_TECHNICAL_ARCHIVE')
        # The Cloud Run store owns one autocommit connection for an execution.
        # Do not open a second connection here: that method does not exist and
        # a failed pattern record must not pause an otherwise valid observer.
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO temporal_pattern_assessments (pattern_assessment_id,created_at,state,source_ids_json,observation_ids_json,rule_version,assignment_id) VALUES (%s,%s,%s,%s,%s,%s,%s)", (assessment_id,datetime.now().astimezone().isoformat(),assessment.state,json.dumps(assessment.source_ids),json.dumps(assessment.observation_ids),assessment.rule_version,assignment_id))
        return assessment_id

    def first_appraisal_by_fingerprint(self, assignment_id: str, fingerprint: str) -> dict[str, object] | None:
        return self._one("SELECT * FROM first_appraisals WHERE assignment_id=%s AND input_fingerprint_sha256=%s", (assignment_id, fingerprint))

    def first_appraisal_count_since(self, assignment_id: str, since: datetime) -> int:
        row = self._one("SELECT COUNT(*) AS count FROM first_appraisals WHERE assignment_id=%s AND created_at>=%s", (assignment_id, since.isoformat()))
        return int(row["count"]) if row else 0

    def append_first_appraisal(self, appraisal_id: str, assignment_id: str, bundle: dict[str, object], status: str, result: dict[str, object] | None, runtime_meta: dict[str, object]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO first_appraisals (appraisal_id,assignment_id,created_at,input_fingerprint_sha256,status,bundle_json,result_json,runtime_meta_json) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (
                appraisal_id, assignment_id, datetime.now(tz=timezone.utc).isoformat(), str(bundle["input_fingerprint_sha256"]), status,
                json.dumps(bundle, sort_keys=True), json.dumps(result, sort_keys=True) if result is not None else None, json.dumps(runtime_meta, sort_keys=True),
            ))

    def append_bounded_research_appraisal(self, research_id: str, assignment_id: str, bundle: dict[str, object], status: str, result: dict[str, object] | None, runtime_meta: dict[str, object]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO bounded_research_appraisals (research_id,assignment_id,created_at,input_fingerprint_sha256,status,bundle_json,result_json,runtime_meta_json) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (
                research_id, assignment_id, datetime.now(tz=timezone.utc).isoformat(), str(bundle["input_fingerprint_sha256"]), status,
                json.dumps(bundle, sort_keys=True), json.dumps(result, sort_keys=True) if result is not None else None, json.dumps(runtime_meta, sort_keys=True),
            ))

    def london_advisories(self, assignment_id: str = "LONDON_FINAL_ACTIVE") -> list[dict[str, object]]:
        rows = self._all(
            "SELECT appraisal_id AS record_id,created_at,result_json,bundle_json,'FIRST_APPRAISAL' AS kind FROM first_appraisals WHERE assignment_id=%s AND status='VALIDATED' "
            "UNION ALL SELECT research_id AS record_id,created_at,result_json,bundle_json,'BOUNDED_RESEARCH' AS kind FROM bounded_research_appraisals WHERE assignment_id=%s AND status='VALIDATED' ORDER BY created_at DESC",
            (assignment_id, assignment_id),
        )
        return [{**row, "result": _json(row["result_json"]), "bundle": _json(row["bundle_json"])} for row in rows]

    def append_strategic_brief(self, brief_id, assignment_id, brief_type, status, evidence_ids, foresight, brief, meta, historical_as_of=None):
        with self.connection.cursor() as cursor: cursor.execute("INSERT INTO strategic_briefs (brief_id,assignment_id,brief_type,created_at,status,evidence_ids_json,foresight_json,brief_json,runtime_meta_json,historical_as_of) VALUES (%s,%s,%s,NOW(),%s,%s,%s,%s,%s,%s)",(brief_id,assignment_id,brief_type,status,json.dumps(evidence_ids),json.dumps(foresight),json.dumps(brief),json.dumps(meta),historical_as_of))

    def strategic_briefs(self, assignment_id="LONDON_FINAL_ACTIVE"):
        rows=self._all("SELECT * FROM strategic_briefs WHERE assignment_id=%s AND status='VALIDATED' ORDER BY created_at DESC",(assignment_id,)); result=[]; seen=set()
        for row in rows:
            key=(row["brief_type"],row.get("historical_as_of"))
            if key in seen: continue
            seen.add(key); result.append({**row,"evidence_ids":_json(row["evidence_ids_json"]),"foresight":_json(row["foresight_json"]),"brief":_json(row["brief_json"]),"runtime_meta":_json(row["runtime_meta_json"])})
        return result

    def create_operator_access_link(self, code_digest: str, expires_at: datetime) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO operator_access_links (code_digest,expires_at) VALUES (%s,%s)",
                (code_digest, expires_at.isoformat()),
            )

    def consume_operator_access_link(self, code_digest: str, now: datetime) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute(
                """UPDATE operator_access_links SET consumed_at=%s
                   WHERE code_digest=%s AND consumed_at IS NULL AND expires_at>=%s""",
                (now.isoformat(), code_digest, now.isoformat()),
            )
            return cursor.rowcount == 1

    def _append_observation_control_event(self, event_type: str, payload: dict[str, object]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO observation_control_events (occurred_at,event_type,payload_json) VALUES (%s,%s,%s)",
                (datetime.now(tz=timezone.utc).isoformat(), event_type, json.dumps(payload, sort_keys=True)))

    def observation_control(self) -> dict[str, object]:
        row = self._one("SELECT * FROM observation_control WHERE control_id=1")
        if row is None: raise RuntimeError("observation control schema is unavailable")
        result = dict(row); result["cycle_active"] = bool(result["cycle_active"])
        result["heartbeat"] = "OBSERVING" if result["cycle_active"] else ("WAITING" if result["state"] == "RUNNING" else result["state"])
        return result

    def start_observation_control(self, cadence_seconds: int) -> dict[str, object]:
        from .observation_control import validate_cadence
        cadence = validate_cadence(cadence_seconds); now = datetime.now(tz=timezone.utc)
        with self.connection.cursor() as cursor:
            cursor.execute("UPDATE observation_control SET state='RUNNING',cadence_seconds=%s,next_observation_at=%s,last_error_class=NULL,updated_at=%s WHERE control_id=1", (cadence,now.isoformat(),now.isoformat()))
        self._append_observation_control_event("control.started", {"cadence_seconds": cadence})
        return self.observation_control()

    def pause_observation_control(self) -> dict[str, object]:
        now=datetime.now(tz=timezone.utc)
        with self.connection.cursor() as cursor: cursor.execute("UPDATE observation_control SET state='PAUSED',updated_at=%s WHERE control_id=1",(now.isoformat(),))
        self._append_observation_control_event("control.paused", {})
        return self.observation_control()

    def resume_observation_control(self) -> dict[str, object]:
        now=datetime.now(tz=timezone.utc)
        with self.connection.cursor() as cursor: cursor.execute("UPDATE observation_control SET state='RUNNING',next_observation_at=%s,last_error_class=NULL,updated_at=%s WHERE control_id=1",(now.isoformat(),now.isoformat()))
        self._append_observation_control_event("control.resumed", {})
        return self.observation_control()

    def stop_observation_control(self) -> dict[str, object]:
        now=datetime.now(tz=timezone.utc)
        with self.connection.cursor() as cursor: cursor.execute("UPDATE observation_control SET state='STOPPED',next_observation_at=NULL,updated_at=%s WHERE control_id=1",(now.isoformat(),))
        self._append_observation_control_event("control.stopped", {})
        return self.observation_control()

    def set_observation_source_health(self, source_health: str) -> None:
        current=self._one("SELECT source_health FROM observation_control WHERE control_id=1")
        if current and current["source_health"] != source_health:
            with self.connection.cursor() as cursor: cursor.execute("UPDATE observation_control SET source_health=%s,updated_at=%s WHERE control_id=1",(source_health,datetime.now(tz=timezone.utc).isoformat()))
            self._append_observation_control_event("source.health", {"source_health": source_health})

    def claim_due_observation_cycle(self, now: datetime) -> bool:
        with self.connection.cursor() as cursor:
            cursor.execute("""UPDATE observation_control SET cycle_active=TRUE,updated_at=%s
                WHERE control_id=1 AND state='RUNNING' AND cycle_active=FALSE
                AND (next_observation_at IS NULL OR next_observation_at<=%s)""",(now.isoformat(),now.isoformat()))
            claimed=cursor.rowcount == 1
        if claimed: self._append_observation_control_event("observation.claimed", {})
        return claimed

    def finish_observation_cycle_claim(self, now: datetime, *, source_health: str, outcome: dict[str, object] | None = None, error_class: str | None = None, pause: bool = False) -> None:
        row=self._one("SELECT cadence_seconds FROM observation_control WHERE control_id=1")
        if row is None: raise RuntimeError("observation control schema is unavailable")
        state="PAUSED" if pause else "RUNNING"; next_at=None if pause else (now + timedelta(seconds=int(row["cadence_seconds"]))).isoformat()
        with self.connection.cursor() as cursor:
            cursor.execute("UPDATE observation_control SET state=%s,cycle_active=FALSE,last_observation_at=%s,next_observation_at=%s,source_health=%s,last_error_class=%s,updated_at=%s WHERE control_id=1",(state,now.isoformat(),next_at,source_health,error_class,now.isoformat()))
        self._append_observation_control_event("observation.failed" if pause else "observation.completed", {"source_health":source_health,"error_class":error_class,"outcome":outcome or {}})

    def execution_attempt(self, execution_id: str) -> dict[str, object] | None:
        row = self._one("SELECT * FROM execution_attempts WHERE execution_id=%s", (execution_id,))
        generic = row is None
        if generic:
            row = self._one("SELECT * FROM case_execution_attempts WHERE execution_id=%s", (execution_id,))
        if row is None:
            return None
        events_table = "case_execution_events" if generic else "execution_events"
        events = self._all(
            f"SELECT occurred_at,event_type,payload_json FROM {events_table} WHERE execution_id=%s ORDER BY event_id",
            (execution_id,),
        )
        result: dict[str, object] = dict(row)
        if generic:
            bundle = self._one("SELECT payload_json FROM governed_evidence_bundles WHERE bundle_id=%s", (result["bundle_id"],))
            payload = _json(bundle["payload_json"]) if bundle else {"evidence": []}
            result["evidence_hashes"] = {item["evidence_id"]: item["content_hash"] for item in payload["evidence"]}
            result["generic_case_execution"] = True
            result["case"] = self.case(str(result["case_id"]))
        else:
            result["evidence_hashes"] = _json(result.pop("evidence_hashes_json"))
        result["events"] = [{"occurred_at": event["occurred_at"], "event_type": event["event_type"], "payload": _json(event["payload_json"])} for event in events]
        return result

    def lead_execution_records(self) -> list[dict[str, object]]:
        rows = self._all("SELECT execution_id FROM execution_attempts ORDER BY created_at DESC")
        rows += self._all("SELECT execution_id FROM case_execution_attempts ORDER BY created_at DESC")
        return [record for row in rows if (record := self.execution_attempt(str(row["execution_id"]))) is not None]

    def case(self, case_id: str) -> dict[str, object] | None:
        row = self._one("SELECT * FROM cases WHERE case_id=%s", (case_id,))
        if row is None:
            return None
        links = self._all("SELECT link_type,link_id FROM case_links WHERE case_id=%s ORDER BY created_at", (case_id,))
        value = dict(row)
        value["metadata"] = _json(value.pop("metadata_json"))
        value["links"] = links
        return value

    def foresight_projection(self) -> dict[str, Any] | None:
        execution = self._one("SELECT foresight_execution_id,source_state_id FROM foresight_executions ORDER BY created_at DESC LIMIT 1")
        if execution is None:
            return None
        events = {
            str(row["event_type"]): _json(row["payload_json"])
            for row in self._all(
                "SELECT event_type,payload_json FROM foresight_execution_events WHERE foresight_execution_id=%s ORDER BY event_id",
                (execution["foresight_execution_id"],),
            )
        }
        if "foresight.governance_persisted" not in events:
            return None
        source = self._one("SELECT payload_json FROM foresight_source_states WHERE source_state_id=%s", (execution["source_state_id"],))
        state = _json(source["payload_json"]) if source else {}
        facts = state.get("facts", [])
        primary = next((fact for fact in facts if str(fact.get("value", "")).startswith("-")), facts[0] if facts else {})
        selected = {
            "case_id": state.get("source_state_id", execution["source_state_id"]), "bundle_id": state.get("bundle_id", "GOVERNED_CASE"),
            "geography": primary.get("geographic_scope", state.get("geography", "Governed geographic scope")),
            "measure": primary.get("measure", "governed observed condition"), "value": primary.get("value", "—"),
            "unit": primary.get("unit", ""), "as_of": primary.get("as_of", ""),
            "limitation": primary.get("limitation", "Evidence limits are retained."),
            "source_ids": [item.get("source_id", "") for item in state.get("sources", [])],
            "fact_ids": [item.get("fact_id", "") for item in facts],
        }
        return {"execution_id": execution["foresight_execution_id"], "assessment": events["foresight.artifact_persisted"],
                "challenge": events["foresight.challenge_artifact_persisted"], "governance": events["foresight.governance_persisted"],
                "scenario": events["foresight.scenarios_persisted"], "selected": selected}

    # The following narrowly scoped methods are the authenticated operator path
    # for accelerated historical replay.  Public handlers never call them.
    def create_accelerated_replay(self, replay_id: str, authorization_reference: str, sequence_version: str) -> None:
        if not authorization_reference.strip(): raise ValueError("replay authorization is required")
        active=self._one("SELECT replay_id FROM accelerated_replays WHERE active=TRUE LIMIT 1")
        if active is not None: raise ValueError("accelerated historical replay already active: " + str(active["replay_id"]))
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO accelerated_replays (replay_id,created_at,status,authorization_reference,sequence_version,active) VALUES (%s,%s,'RUNNING',%s,%s,TRUE)",
                (replay_id,datetime.now().astimezone().isoformat(),authorization_reference,sequence_version))

    def append_accelerated_replay_event(self, replay_id: str, event_type: str, message: str, payload: dict[str, object]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO accelerated_replay_events (replay_id,occurred_at,event_type,message,payload_json) VALUES (%s,%s,%s,%s,%s)",
                (replay_id,datetime.now().astimezone().isoformat(),event_type,message,json.dumps(payload,sort_keys=True)))

    def create_accelerated_replay_snapshot(self, replay_id: str, item, inserted_at: datetime) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO accelerated_replay_snapshots (replay_id,replay_sequence,source_id,source_reference,source_date,content_hash,evidence_class,inserted_at,state) VALUES (%s,%s,%s,%s,%s,%s,'REAL',%s,'INTRODUCED')",
                (replay_id,item.replay_sequence,item.source_id,item.source_reference,item.source_date.isoformat(),item.content_hash,inserted_at.isoformat()))

    def update_accelerated_replay_snapshot(self, replay_id: str, sequence: int, state: str, **links: str) -> None:
        allowed={"signal_id","attention","candidate_signal_id","case_id","execution_id"}
        if set(links).difference(allowed): raise ValueError("unsupported accelerated replay link")
        assignments=["state=%s"]; values: list[object]=[state]
        for key,value in links.items(): assignments.append(key+"=%s"); values.append(value)
        values += [replay_id,sequence]
        with self.connection.cursor() as cursor:
            cursor.execute("UPDATE accelerated_replay_snapshots SET " + ",".join(assignments) + " WHERE replay_id=%s AND replay_sequence=%s",values)
            if cursor.rowcount != 1: raise ValueError("unknown accelerated replay snapshot")

    def accelerated_replay(self, replay_id: str | None = None) -> dict[str, object] | None:
        row=self._one("SELECT * FROM accelerated_replays " + ("WHERE replay_id=%s" if replay_id else "ORDER BY created_at DESC LIMIT 1"), (replay_id,) if replay_id else ())
        if row is None: return None
        snapshots=self._all("SELECT * FROM accelerated_replay_snapshots WHERE replay_id=%s ORDER BY replay_sequence",(row["replay_id"],))
        events=self._all("SELECT occurred_at,event_type,message,payload_json FROM accelerated_replay_events WHERE replay_id=%s ORDER BY event_id",(row["replay_id"],))
        return {**row,"snapshots":snapshots,"events":[{**event,"payload":_json(event["payload_json"])} for event in events]}

    def complete_accelerated_replay(self, replay_id: str, status: str) -> None:
        if status not in {"COMPLETED","STOPPED"}: raise ValueError("invalid accelerated replay terminal state")
        with self.connection.cursor() as cursor:
            cursor.execute("UPDATE accelerated_replays SET status=%s,active=FALSE WHERE replay_id=%s AND active=TRUE",(status,replay_id))
            if cursor.rowcount != 1: raise ValueError("accelerated replay is not active")

    def record_signal(self, snapshot, signal_id: str, eligibility: str) -> None:
        if eligibility not in {"IGNORE", "WATCH", "ATTENTION_PENDING"}: raise ValueError("unsupported deterministic signal eligibility")
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO signals (signal_id,source_id,source_hash,source_reference,source_date,evidence_class,eligibility,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (signal_id,snapshot.source_id,snapshot.content_hash,snapshot.source_reference,snapshot.source_date.isoformat(),snapshot.evidence_class.value,eligibility,snapshot.observed_at.isoformat()))

    def signal(self, signal_id: str) -> dict[str, object] | None:
        return self._one("SELECT * FROM signals WHERE signal_id=%s",(signal_id,))

    def signal_for_source_hash(self, source_id: str, source_hash: str) -> dict[str, object] | None:
        return self._one("SELECT * FROM signals WHERE source_id=%s AND source_hash=%s", (source_id, source_hash))

    def attention(self, signal_id: str) -> dict[str, object] | None:
        return self._one("SELECT * FROM attention_assessments WHERE signal_id=%s", (signal_id,))

    def candidate_for_deduplication_key(self, key: str):
        return self.candidate_by_key(key)

    def record_attention(self, signal_id: str, decision: str, reason: str, attention_id: str) -> None:
        if decision not in {"IGNORE","WATCH","INVESTIGATE"} or not reason.strip(): raise ValueError("invalid attention decision")
        if self.signal(signal_id) is None: raise ValueError("attention requires a persisted signal")
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO attention_assessments (attention_id,signal_id,decision,reason,created_at) VALUES (%s,%s,%s,%s,%s)",
                (attention_id,signal_id,decision,reason,datetime.now().astimezone().isoformat()))

    def record_candidate(self, candidate) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO candidate_signals (signal_id,source_id,observed_hash,observed_date,deduplication_key,provenance_reference,replay_sequence,triage_state) VALUES (%s,%s,%s,%s,%s,%s,%s,'CANDIDATE')",
                (candidate.signal_id,candidate.source_id,candidate.observed_hash,candidate.observed_date.isoformat(),candidate.deduplication_key,candidate.provenance_reference,candidate.replay_sequence))

    def candidate(self, signal_id: str):
        from .observation import CandidateSignal
        row=self._one("SELECT * FROM candidate_signals WHERE signal_id=%s",(signal_id,))
        if row is None: return None
        return CandidateSignal(str(row["signal_id"]),str(row["source_id"]),str(row["observed_hash"]),datetime.fromisoformat(str(row["observed_date"])),str(row["deduplication_key"]),str(row["provenance_reference"]),int(row["replay_sequence"]))

    def candidate_by_key(self, key: str):
        row=self._one("SELECT signal_id FROM candidate_signals WHERE deduplication_key=%s", (key,))
        return self.candidate(str(row["signal_id"])) if row else None

    def create_case(self, case_id: str, *, title: str, label: str, case_mode: str, source_observation_mode: str, metadata: dict[str, object]) -> None:
        if not all((case_id,title.strip(),label.strip(),case_mode,source_observation_mode)): raise ValueError("generic case identity is incomplete")
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO cases (case_id,created_at,case_mode,title,label,source_observation_mode,status,metadata_json) VALUES (%s,%s,%s,%s,%s,%s,'OPEN',%s)",
                (case_id,datetime.now().astimezone().isoformat(),case_mode,title,label,source_observation_mode,json.dumps(metadata,sort_keys=True)))

    def link_case(self, case_id: str, link_type: str, link_id: str) -> None:
        if link_type not in {"SIGNAL","CANDIDATE","EXECUTION","FORESIGHT_SOURCE_STATE","FORESIGHT_EXECUTION"}: raise ValueError("unsupported generic case link")
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO case_links (case_id,link_type,link_id,created_at) VALUES (%s,%s,%s,%s)",
                (case_id,link_type,link_id,datetime.now().astimezone().isoformat()))

    def persist_evidence_bundle(self, bundle: dict[str, object]) -> None:
        evidence=bundle.get("evidence",[])
        if not bundle.get("bundle_id") or not bundle.get("case_id") or not isinstance(evidence,list) or not evidence: raise ValueError("governed evidence bundle is incomplete")
        if any(len(str(item.get("content_hash",""))) != 64 for item in evidence): raise ValueError("governed evidence bundle integrity is invalid")
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO governed_evidence_bundles (bundle_id,case_id,created_at,integrity_verified,payload_json) VALUES (%s,%s,%s,TRUE,%s)",
                (str(bundle["bundle_id"]),str(bundle["case_id"]),datetime.now().astimezone().isoformat(),json.dumps(bundle,sort_keys=True)))

    def create_case_execution(self, execution: dict[str, object]) -> None:
        required={"execution_id","case_id","candidate_signal_id","bundle_id","execution_mode","source_observation_mode","authorization_reference"}
        if not required.issubset(execution) or not str(execution["authorization_reference"]).strip(): raise ValueError("generic case execution is incomplete")
        if self.candidate(str(execution["candidate_signal_id"])) is None: raise ValueError("generic case execution candidate is invalid")
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO case_execution_attempts (execution_id,case_id,candidate_signal_id,bundle_id,created_at,execution_mode,source_observation_mode,authorization_reference) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (str(execution["execution_id"]),str(execution["case_id"]),str(execution["candidate_signal_id"]),str(execution["bundle_id"]),datetime.now().astimezone().isoformat(),str(execution["execution_mode"]),str(execution["source_observation_mode"]),str(execution["authorization_reference"])))
        self.link_case(str(execution["case_id"]),"EXECUTION",str(execution["execution_id"]))

    def append_execution_event(self, execution_id: str, occurred_at: datetime, event_type: str, payload: dict[str, object]) -> None:
        if self._one("SELECT execution_id FROM case_execution_attempts WHERE execution_id=%s",(execution_id,)) is None: raise ValueError("cannot append an event for an unknown generic execution")
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO case_execution_events (execution_id,occurred_at,event_type,payload_json) VALUES (%s,%s,%s,%s)",
                (execution_id,occurred_at.isoformat(),event_type,json.dumps(payload,sort_keys=True)))

    def persist_execution_initial_plan(self, execution_id: str, plan: dict[str, object]) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO execution_initial_plans (plan_id,execution_id,created_at,payload_json) VALUES (%s,%s,%s,%s)",
                ("plan-"+execution_id.split("-")[-1],execution_id,datetime.now().astimezone().isoformat(),json.dumps(plan,sort_keys=True)))

    # These methods intentionally make accidental Cloud Run mutation impossible.
    def __getattr__(self, name: str) -> Any:
        if name.startswith(("create_", "record_", "reserve_", "append_", "save_", "persist_", "link_")):
            raise RuntimeError("Cloud Run judge storage is read-only")
        raise AttributeError(name)

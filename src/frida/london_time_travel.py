"""Visible, model-free playback of the frozen London development chronology."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from threading import Thread
from time import sleep
from uuid import uuid4


MODE = "LONDON_ACCELERATED_HISTORICAL_REPLAY"
SEQUENCE_VERSION = "LONDON_SW8_TIME_TRAVEL_v1"


@dataclass(frozen=True, slots=True)
class LondonHistoricalStep:
    replay_sequence: int
    source_id: str
    source_reference: str
    source_date: datetime
    facts: dict[str, object]

    @property
    def content_hash(self) -> str:
        return sha256(json.dumps(self.facts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


SEQUENCE = (
    LondonHistoricalStep(1, "PLANNING_LONDON_DATAHUB", "Wandsworth-2005_4426", datetime(2006,11,24,tzinfo=UTC), {"record":"Wandsworth-2005_4426","place":"Battersea Power Station and South Lambeth Goods Yard","development_type":"New Build","status":"Lapsed","decision_date":"2006-11-24"}),
    LondonHistoricalStep(2, "PLANNING_LONDON_DATAHUB", "Wandsworth-2017_7069", datetime(2018,10,25,tzinfo=UTC), {"record":"Wandsworth-2017_7069","place":"Embassy Gardens Phase 2","development_type":"New Build","status":"Completed","decision_date":"2018-10-25","actual_start_date":"2018-10-25","actual_completion_date":"2021-12-01"}),
    LondonHistoricalStep(3, "PLANNING_LONDON_DATAHUB", "Wandsworth-2020_3867", datetime(2021,4,15,tzinfo=UTC), {"record":"Wandsworth-2020_3867","place":"Battersea Gasholder, 101 Prince of Wales Drive","status":"Completed","decision_date":"2021-04-15","actual_start_date":"2021-04-15","actual_completion_date":"2024-03-31"}),
    LondonHistoricalStep(4, "TRANSPORT_FOR_LONDON", "Victoria line status", datetime(2026,8,27,tzinfo=UTC), {"line":"victoria","context":"Vauxhall / Victoria line","status":"Good Service","source_timestamp":"2026-08-27T12:26:42Z"}),
    LondonHistoricalStep(5, "ENVIRONMENT_AGENCY", "Westminster Thames Tideway station 0006", datetime(2026,8,29,tzinfo=UTC), {"station":"0006","measure":"0006-level-tidal_level-i-15_min-mAOD","value":-1.393,"unit":"mAOD","source_timestamp":"2026-08-29T23:15:00Z"}),
)


class LondonTimeTravel:
    def __init__(self, store):
        self.store=store

    def start(self, authorization_reference: str, *, step_seconds: float = 3.2) -> str:
        replay_id="london-time-travel-"+uuid4().hex
        self.store.create_accelerated_replay(replay_id, authorization_reference, SEQUENCE_VERSION)
        self.store.append_accelerated_replay_event(replay_id,"replay.started","London Time Travel started",{"execution_mode":MODE,"source_observation_mode":"HISTORICAL_REAL","sequence_version":SEQUENCE_VERSION,"semantic_calls":0})
        def progress() -> None:
            try:
                for step in SEQUENCE:
                    sleep(step_seconds)
                    now=datetime.now(tz=UTC)
                    self.store.create_accelerated_replay_snapshot(replay_id, step, now)
                    self.store.append_accelerated_replay_event(replay_id,"time_travel.observation","Historical London evidence observed",{"replay_sequence":step.replay_sequence,"historical_evidence_time":step.source_date.isoformat(),"replay_execution_time":now.isoformat(),"source_id":step.source_id,"source_reference":step.source_reference,"content_hash":step.content_hash,"semantic_calls":0})
                    self.store.update_accelerated_replay_snapshot(replay_id,step.replay_sequence,"OBSERVED_NO_STRATEGIC_DISPATCH")
                    self.store.append_accelerated_replay_event(replay_id,"time_travel.no_dispatch","Historical transition retained without strategic dispatch",{"replay_sequence":step.replay_sequence,"reason":"no temporal-pattern eligibility policy is authorized","semantic_calls":0})
                self.store.append_accelerated_replay_event(replay_id,"replay.completed","London Time Travel completed",{"semantic_calls":0,"retry_count":0})
                self.store.complete_accelerated_replay(replay_id,"COMPLETED")
            except Exception as error:
                record=self.store.accelerated_replay(replay_id)
                if record and record.get("status")=="RUNNING":
                    self.store.append_accelerated_replay_event(replay_id,"replay.stopped","London Time Travel stopped",{"error_class":type(error).__name__,"semantic_calls":0,"retry_count":0})
                    self.store.complete_accelerated_replay(replay_id,"STOPPED")
        Thread(target=progress,name='frida-london-time-travel',daemon=True).start()
        return replay_id

"""Governed, non-live playback of approved historical DENUE evidence.

The coordinator is intentionally inert until an authenticated controller calls
it.  It records replay time separately from the original evidence time and
never repurposes a replay snapshot as a new World Observation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import Thread
from time import sleep
from uuid import uuid4

from .domain import EvidenceClass
from .observation import ReplaySnapshot

MODE = "ACCELERATED_HISTORICAL_REPLAY"
SEQUENCE_VERSION = "DENUE_QRO_0525_0526_v1"


@dataclass(frozen=True, slots=True)
class ApprovedHistoricalSnapshot:
    replay_sequence: int
    source_id: str
    source_reference: str
    source_date: datetime
    content_hash: str
    relative_file: str

    def verify(self, root: Path) -> None:
        target = root / self.relative_file
        if not target.is_file():
            raise ValueError(f"approved historical source is unavailable: {self.relative_file}")
        digest = sha256(target.read_bytes()).hexdigest()
        if digest != self.content_hash:
            raise ValueError(f"approved historical source hash mismatch: {self.relative_file}")

    def snapshot(self, now: datetime) -> ReplaySnapshot:
        return ReplaySnapshot(
            source_id=self.source_id, source_reference=self.source_reference,
            source_date=self.source_date, content_hash=self.content_hash,
            evidence_class=EvidenceClass.REAL, replay_sequence=self.replay_sequence,
            observed_at=now,
        )


@dataclass(frozen=True, slots=True)
class AttentionSignal:
    """A persisted Signal-shaped input, deliberately not a Candidate."""
    signal_id: str
    source_id: str
    observed_hash: str
    observed_date: datetime
    provenance_reference: str
    replay_sequence: int


APPROVED_SEQUENCE = (
    ApprovedHistoricalSnapshot(1, "DENUE", "INEGI DENUE 05/2025 Querétaro edition", datetime(2025, 5, 1, tzinfo=UTC),
        "dc7d317aaf846cf4c58213fdf8d72f8635ade40fee0216a9a145580fa721e0e0", "denue_22_0525_csv.zip"),
    ApprovedHistoricalSnapshot(2, "DENUE", "INEGI DENUE 05/2026 corrected edition", datetime(2026, 7, 1, tzinfo=UTC),
        "2ea1e298086f109cdbdb6a036d6cd3ecfbdfe26123b34248d73b1d06c201304a", "denue_22_0526_corrected_csv.zip"),
)


def verify_approved_sequence(root: str | Path) -> tuple[ApprovedHistoricalSnapshot, ...]:
    base = Path(root)
    for item in APPROVED_SEQUENCE:
        item.verify(base)
    return APPROVED_SEQUENCE


class AcceleratedHistoricalReplay:
    """Deterministic playback up to the model-bearing Attention boundary."""

    def __init__(self, store, evidence_root: str | Path):
        self.store, self.evidence_root = store, Path(evidence_root)

    def start(self, authorization_reference: str) -> str:
        verify_approved_sequence(self.evidence_root)
        replay_id = "replay-" + uuid4().hex
        self.store.create_accelerated_replay(replay_id, authorization_reference, SEQUENCE_VERSION)
        self.store.append_accelerated_replay_event(replay_id, "replay.started", "Accelerated historical replay started", {
            "execution_mode": MODE, "source_observation_mode": "HISTORICAL_REAL", "sequence_version": SEQUENCE_VERSION,
        })
        return replay_id

    def process_deterministic_snapshot(self, replay_id: str, replay_sequence: int, now: datetime | None = None) -> dict[str, object]:
        """Advance one approved snapshot; seq 2 stops at Attention, never dispatching a model here."""
        now = now or datetime.now(tz=UTC)
        self.introduce_snapshot(replay_id, replay_sequence, now)
        return self.classify_introduced_snapshot(replay_id, replay_sequence, now)

    def introduce_snapshot(self, replay_id: str, replay_sequence: int, now: datetime | None = None) -> None:
        """Persist one real historical source examination, without classifying it yet."""
        now = now or datetime.now(tz=UTC)
        item = next((value for value in APPROVED_SEQUENCE if value.replay_sequence == replay_sequence), None)
        if item is None:
            raise ValueError("replay sequence is not approved")
        item.verify(self.evidence_root)
        self.store.create_accelerated_replay_snapshot(replay_id, item, now)
        self.store.append_accelerated_replay_event(replay_id, "observe.source_examined", "Approved historical source snapshot examined", {
            "replay_sequence": item.replay_sequence, "historical_evidence_time": item.source_date.isoformat(),
            "replay_execution_time": now.isoformat(), "content_hash": item.content_hash,
        })

    def classify_introduced_snapshot(self, replay_id: str, replay_sequence: int, now: datetime | None = None) -> dict[str, object]:
        """Persist the deterministic classification for an already observed snapshot."""
        now = now or datetime.now(tz=UTC)
        item = next((value for value in APPROVED_SEQUENCE if value.replay_sequence == replay_sequence), None)
        if item is None:
            raise ValueError("replay sequence is not approved")
        record = self.store.accelerated_replay(replay_id)
        if record is None or not any(int(row["replay_sequence"]) == replay_sequence and row["state"] == "INTRODUCED" for row in record["snapshots"]):
            raise ValueError("replay snapshot must be introduced before classification")
        if item.replay_sequence == 1:
            self.store.update_accelerated_replay_snapshot(replay_id, item.replay_sequence, "NO_ELIGIBLE_SIGNAL")
            self.store.append_accelerated_replay_event(replay_id, "signal.none", "Baseline snapshot established; no eligible change signal", {
                "reason": "first approved historical baseline", "semantic_calls": 0,
            })
            return {"state": "NO_ELIGIBLE_SIGNAL", "replay_sequence": item.replay_sequence}
        existing = self.store.signal_for_source_hash(item.source_id, item.content_hash)
        signal_id = str(existing["signal_id"]) if existing else "signal-replay-" + sha256(f"{replay_id}:{item.source_id}:{item.content_hash}".encode()).hexdigest()[:20]
        if existing is None:
            self.store.record_signal(item.snapshot(now), signal_id, "ATTENTION_PENDING")
        self.store.update_accelerated_replay_snapshot(replay_id, item.replay_sequence, "ATTENTION_PENDING", signal_id=signal_id)
        self.store.append_accelerated_replay_event(replay_id, "signal.detected", "Edition change detected; FRIDA Attention is required", {
            "signal_id": signal_id, "canonical_signal_reused": existing is not None, "replay_sequence": item.replay_sequence,
            "historical_evidence_time": item.source_date.isoformat(), "semantic_calls": 0,
        })
        return {"state": "ATTENTION_PENDING", "replay_sequence": item.replay_sequence, "signal_id": signal_id}

    def start_live_deterministic_progression(self, authorization_reference: str, *, step_seconds: float = 3.2) -> str:
        """Run genuine replay transitions in separate observable cycles; never dispatch a model."""
        replay_id = self.start(authorization_reference)

        def progress() -> None:
            try:
                for action in (
                    lambda: self.introduce_snapshot(replay_id, 1),
                    lambda: self.classify_introduced_snapshot(replay_id, 1),
                    lambda: self.introduce_snapshot(replay_id, 2),
                    lambda: self.classify_introduced_snapshot(replay_id, 2),
                    lambda: self.stop_deterministic_verification(replay_id),
                ):
                    sleep(step_seconds)
                    action()
            except Exception as error:
                record = self.store.accelerated_replay(replay_id)
                if record is not None and record["status"] == "RUNNING":
                    self.store.append_accelerated_replay_event(replay_id, "replay.stopped", "Deterministic replay progression stopped", {"error_class": type(error).__name__, "retry_count": 0, "semantic_calls": 0})
                    self.store.complete_accelerated_replay(replay_id, "STOPPED")

        Thread(target=progress, name=f"frida-replay-{replay_id[-8:]}", daemon=True).start()
        return replay_id

    def stop_deterministic_verification(self, replay_id: str) -> None:
        """Close a model-free projection check without advancing to Attention runtime."""
        record = self.store.accelerated_replay(replay_id)
        if record is None or record["status"] != "RUNNING":
            raise ValueError("accelerated replay is not active")
        self.store.append_accelerated_replay_event(replay_id, "replay.stopped", "Deterministic live-projection verification completed", {
            "reason": "deterministic_verification_complete", "retry_count": 0, "semantic_calls": 0,
        })
        self.store.complete_accelerated_replay(replay_id, "STOPPED")

    def run_authorized_semantic_path(self, replay_id: str, evidence, authorization_reference: str, stages=None) -> dict[str, object]:
        """Future-only bounded positive path; callers require separate runtime clearance.

        The persisted Signal goes to FRIDA Attention first.  A Candidate is
        created only if that validated decision is INVESTIGATE; the prefetched
        result is then reused by Option 2.5, avoiding a duplicate model call.
        """
        from .case_spine import CaseSpine
        from .lead_runtime import execute_lead_case
        from .native_stage_runtime import NativeStages

        record=self.store.accelerated_replay(replay_id)
        if record is None or record["status"] != "RUNNING": raise ValueError("accelerated replay is not runnable")
        snapshot=next((item for item in record["snapshots"] if item["state"] == "ATTENTION_PENDING"),None)
        if snapshot is None: raise ValueError("accelerated replay has no pending attention signal")
        approved=next(item for item in APPROVED_SEQUENCE if item.replay_sequence == int(snapshot["replay_sequence"]))
        approved.verify(self.evidence_root)
        signal=AttentionSignal(str(snapshot["signal_id"]),approved.source_id,approved.content_hash,approved.source_date,approved.source_reference,approved.replay_sequence)
        owned=stages is None; stages=stages or NativeStages()
        try:
            spine=CaseSpine(self.store)
            canonical_attention=self.store.attention(signal.signal_id)
            if canonical_attention is None:
                attention_result, meta=stages.lead_attention(signal,evidence)
                self.store.append_accelerated_replay_event(replay_id,"frida.attention_completed","FRIDA Attention completed",{"decision":attention_result["attention"],"usage":meta.get("usage",{}),"latency_ms":meta.get("latency_ms",0),"configured_max_output_tokens":meta.get("configured_max_output_tokens",4096)})
                decision,reason=attention_result["attention"],attention_result["reason"]
            else:
                decision,reason=str(canonical_attention["decision"]),str(canonical_attention["reason"])
                self.store.append_accelerated_replay_event(replay_id,"frida.attention_reused","Canonical FRIDA Attention disposition reused",{"decision":decision,"attention_id":canonical_attention["attention_id"],"semantic_calls":0})
            result=spine.resolve_attention(signal.signal_id,decision,reason,title="Accelerated historical DENUE case",label="ACCELERATED HISTORICAL REPLAY · HISTORICAL REAL",metadata={"replay_id":replay_id,"historical_evidence_time":approved.source_date.isoformat(),"source_hash":approved.content_hash},case_mode=MODE,source_observation_mode=MODE)
            if result["attention"] != "INVESTIGATE":
                self.store.update_accelerated_replay_snapshot(replay_id,approved.replay_sequence,"COMPLETED_"+str(result["attention"]),attention=str(result["attention"]))
                self.store.append_accelerated_replay_event(replay_id,"replay.completed","Replay completed without Candidate or specialist dispatch",{"attention":result["attention"],"semantic_calls":1})
                self.store.complete_accelerated_replay(replay_id,"COMPLETED")
                return {"state":"COMPLETED_"+str(result["attention"]),"semantic_calls":1}
            candidate=result["candidate_signal"]
            def live_event(event_type, payload):
                if event_type in {"stage.started", "stage.model_completed", "stage.gate_opened", "stage.gate_blocked", "disposition.completed", "execution.stopped"}:
                    stage = str(payload.get("stage", "Governance"))
                    message = {"stage.started": f"{stage} started", "stage.model_completed": f"{stage} completed", "stage.gate_opened": f"{stage} authorized", "stage.gate_blocked": f"{stage} blocked", "disposition.completed": "Governance result issued", "execution.stopped": f"{stage} stopped"}[event_type]
                    self.store.append_accelerated_replay_event(replay_id, event_type, message, {"stage": stage, "execution_id": payload.get("execution_id"), "disposition": payload.get("disposition"), "retry_count": payload.get("retry_count", 0)})
            execution_id,outcome=execute_lead_case(self.store,str(result["case_id"]),candidate,evidence,authorization_reference,stages,execution_mode=MODE,source_observation_mode=MODE,expected_attention="INVESTIGATE",event_sink=live_event)
            self.store.update_accelerated_replay_snapshot(replay_id,approved.replay_sequence,"COMPLETED",attention="INVESTIGATE",candidate_signal_id=candidate.signal_id,case_id=str(result["case_id"]),execution_id=execution_id)
            self.store.append_accelerated_replay_event(replay_id,"replay.completed","Option 2.5 execution completed",{"execution_id":execution_id,"semantic_calls":outcome.get("semantic_calls",None),"state":outcome["state"]})
            self.store.complete_accelerated_replay(replay_id,"COMPLETED")
            return {"state":outcome["state"],"execution_id":execution_id,"case_id":result["case_id"]}
        except Exception as error:
            self.store.append_accelerated_replay_event(replay_id,"replay.stopped","Replay stopped at governed runtime boundary",{"error_class":type(error).__name__,"retry_count":0})
            self.store.complete_accelerated_replay(replay_id,"STOPPED")
            raise
        finally:
            if owned: stages.close()

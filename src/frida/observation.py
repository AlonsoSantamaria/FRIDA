"""Deterministic autonomous observation and replay integrity for Golden Path v1.0."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Iterable
from .domain import EvidenceClass
from .domain import Initiator, Investigation, InvestigationState

@dataclass(frozen=True, slots=True)
class ReplaySnapshot:
    source_id: str; source_reference: str; source_date: datetime; content_hash: str
    evidence_class: EvidenceClass; replay_sequence: int; observed_at: datetime
    def __post_init__(self):
        if not self.content_hash or self.replay_sequence < 1: raise ValueError("immutable replay snapshot requires hash and positive sequence")

@dataclass(frozen=True, slots=True)
class CandidateSignal:
    signal_id: str; source_id: str; observed_hash: str; observed_date: datetime
    deduplication_key: str; provenance_reference: str; replay_sequence: int

@dataclass(frozen=True, slots=True)
class ObservationAuditEvent:
    event_type: str; source_id: str; detail: str

@dataclass(frozen=True, slots=True)
class ObservationResult:
    candidate_signal: CandidateSignal | None; triage_pending: bool; filtered_reason: str | None
    audit: tuple[ObservationAuditEvent, ...]

class SharedObserver:
    """One mechanism reused by DENUE and Semáforo source configurations."""
    def __init__(self, source_id: str): self.source_id, self._seen = source_id, set()
    def observe(self, snapshot: ReplaySnapshot) -> CandidateSignal | None:
        if snapshot.source_id != self.source_id: raise ValueError("snapshot source mismatch")
        key = sha256(f"{snapshot.source_id}:{snapshot.content_hash}".encode()).hexdigest()
        if key in self._seen: return None
        self._seen.add(key)
        return CandidateSignal("signal-" + key[:16], snapshot.source_id, snapshot.content_hash, snapshot.observed_at, key, snapshot.source_reference, snapshot.replay_sequence)

class HistoricalReplay:
    def __init__(self, snapshots: Iterable[ReplaySnapshot]):
        self.snapshots = tuple(sorted(snapshots, key=lambda x: x.replay_sequence))
        if len({x.replay_sequence for x in self.snapshots}) != len(self.snapshots): raise ValueError("replay sequences must be unique")
    def run(self, observer: SharedObserver) -> list[CandidateSignal]:
        return [s for snapshot in self.snapshots if (s := observer.observe(snapshot)) is not None]

class DenueObserver(SharedObserver):
    def __init__(self): super().__init__("DENUE")

class SemaforoObserver(SharedObserver):
    def __init__(self): super().__init__("SEMAFORO")

def validate_and_prepare(observer: SharedObserver, snapshot: ReplaySnapshot) -> ObservationResult:
    audit = [ObservationAuditEvent("observation.received", snapshot.source_id, snapshot.content_hash)]
    if snapshot.evidence_class is EvidenceClass.SIMULATED:
        audit.append(ObservationAuditEvent("observation.filtered", snapshot.source_id, "unsupported_observer_source"))
        return ObservationResult(None, False, "unsupported_observer_source", tuple(audit))
    signal = observer.observe(snapshot)
    if signal is None:
        audit.append(ObservationAuditEvent("candidate.deduplicated", snapshot.source_id, "known_hash"))
        return ObservationResult(None, False, "duplicate", tuple(audit))
    audit += [ObservationAuditEvent("candidate.created", snapshot.source_id, signal.signal_id), ObservationAuditEvent("semantic_triage.pending", snapshot.source_id, signal.signal_id)]
    return ObservationResult(signal, True, None, tuple(audit))

def open_approved_fixture_investigation(signal: CandidateSignal, now: datetime) -> Investigation:
    """Explicit test-only deterministic boundary; production relevance remains model triage."""
    result = Investigation("investigation-" + signal.signal_id, Initiator.FRIDA, now, InvestigationState.INVESTIGATING)
    result.audit.append("initiation:approved_fixture:" + signal.signal_id)
    return result

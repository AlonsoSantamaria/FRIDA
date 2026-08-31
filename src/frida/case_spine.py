"""Generic, governed Case / Execution spine.

This module owns linkage only.  It never substitutes semantic judgment, copies
evidence, or changes historical replay semantics.
"""
from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from .domain import Evidence, EvidenceClass
from .observation import CandidateSignal, ReplaySnapshot


def _id(prefix: str) -> str:
    return prefix + "-" + uuid4().hex


def signal_id(snapshot: ReplaySnapshot) -> str:
    return "signal-" + sha256(f"{snapshot.source_id}:{snapshot.content_hash}".encode()).hexdigest()[:20]


def evidence_bundle(case_id: str, evidence: tuple[Evidence, ...], bundle_id: str | None = None) -> dict[str, object]:
    """Canonical generic evidence representation, retaining only governed provenance."""
    return {
        "bundle_id": bundle_id or _id("bundle"), "case_id": case_id,
        "evidence": [{
            "evidence_id": item.evidence_id, "content_hash": item.content_hash,
            "source_id": item.source_id, "source_reference": item.source_reference,
            "limitations": list(item.payload.get("limitations", [])) if isinstance(item.payload, dict) else [],
            "evidence_class": item.evidence_class.value,
        } for item in evidence],
    }


class CaseSpine:
    """Coordinates observation → signal → attention → candidate → case.

    Attention is deliberately an explicit governed decision.  Ingestion creates
    no Candidate until the decision is INVESTIGATE.
    """
    def __init__(self, store): self.store = store

    def observe(self, snapshot: ReplaySnapshot) -> dict[str, object]:
        if not self.store.reserve_observation(snapshot):
            return {"state": "DUPLICATE", "signal_id": None, "candidate_signal": None}
        sid = signal_id(snapshot)
        eligibility = "IGNORE" if snapshot.evidence_class is EvidenceClass.SIMULATED else "ATTENTION_PENDING"
        self.store.record_signal(snapshot, sid, eligibility)
        return {"state": eligibility, "signal_id": sid, "candidate_signal": None}

    def resolve_attention(self, signal_id_value: str, decision: str, reason: str,
                          *, title: str, label: str, metadata: dict[str, object] | None = None,
                          case_mode: str = "OBSERVATION", source_observation_mode: str = "LIVE_OBSERVED") -> dict[str, object]:
        signal = self.store.signal(signal_id_value)
        if signal is None: raise ValueError("FRIDA Attention requires an existing signal")
        canonical_attention=self.store.attention(signal_id_value)
        if canonical_attention is None:
            self.store.record_attention(signal_id_value, decision, reason, _id("attention"))
        elif str(canonical_attention["decision"]) != decision:
            raise ValueError("canonical Attention disposition conflicts with replay result")
        if decision != "INVESTIGATE":
            return {"attention": decision, "candidate_signal": None, "case_id": None}
        key=sha256(f"{signal['source_id']}:{signal['source_hash']}".encode()).hexdigest()
        candidate=CandidateSignal("candidate-" + key[:20], str(signal["source_id"]), str(signal["source_hash"]),
            datetime.fromisoformat(str(signal["source_date"])), key, str(signal["source_reference"]), 1)
        existing=self.store.candidate_for_deduplication_key(key)
        candidate=existing or candidate
        if existing is None:
            self.store.record_candidate(candidate)
        case_id=_id("case")
        self.store.create_case(case_id, title=title, label=label, case_mode=case_mode, source_observation_mode=source_observation_mode, metadata=metadata or {})
        self.store.link_case(case_id, "SIGNAL", signal_id_value)
        self.store.link_case(case_id, "CANDIDATE", candidate.signal_id)
        return {"attention": decision, "candidate_signal": candidate, "case_id": case_id}

    def register_execution(self, case_id: str, candidate: CandidateSignal, evidence: tuple[Evidence, ...], authorization_reference: str,
                           *, execution_mode: str = "LIVE_CASE", source_observation_mode: str = "LIVE_OBSERVED") -> str:
        bundle=evidence_bundle(case_id, evidence)
        self.store.persist_evidence_bundle(bundle)
        execution_id=_id("exec-case")
        self.store.create_case_execution({
            "execution_id": execution_id, "case_id": case_id, "candidate_signal_id": candidate.signal_id,
            "bundle_id": bundle["bundle_id"], "execution_mode": execution_mode, "source_observation_mode": source_observation_mode,
            "authorization_reference": authorization_reference,
        })
        self.store.append_execution_event(execution_id, datetime.now(tz=UTC), "execution.registered", {
            "architecture": "REVISED_TARGET_B_OPTION_2_5", "execution_mode": execution_mode,
            "source_observation_mode": source_observation_mode, "claims_new_world_observation": False,
        })
        return execution_id

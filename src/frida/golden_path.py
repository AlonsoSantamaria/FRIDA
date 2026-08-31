"""The first governed FRIDA Golden Path, without a runtime-model dependency.

Agent adapters are injected.  This keeps observation and disposition
deterministic and lets tests exercise the complete vertical slice with fakes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Protocol

from .domain import (
    Challenge, ChallengeMateriality, Evidence, EvidenceClass, GeographicConfidence,
    Initiator, Investigation, InvestigationState, StrategicDisposition,
)
from .governance import evaluate
from .observation import CandidateSignal


def _required(data: dict[str, Any], *names: str) -> None:
    missing = [name for name in names if data.get(name) in (None, "", [])]
    if missing:
        raise ValueError("structured task result missing: " + ", ".join(missing))


@dataclass(frozen=True, slots=True)
class TriageDecision:
    warrants_investigation: bool
    reason: str
    relevant_evidence_ids: tuple[str, ...]
    uncertainties: tuple[str, ...]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "TriageDecision":
        _required(data, "warrants_investigation", "reason", "relevant_evidence_ids", "uncertainties")
        if not isinstance(data["warrants_investigation"], bool):
            raise ValueError("triage warrants_investigation must be boolean")
        return cls(data["warrants_investigation"], str(data["reason"]), tuple(map(str, data["relevant_evidence_ids"])), tuple(map(str, data["uncertainties"])))


@dataclass(frozen=True, slots=True)
class InvestigationAnalysis:
    claims: tuple[str, ...]
    limitations: tuple[str, ...]
    alternative_explanations: tuple[str, ...]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "InvestigationAnalysis":
        _required(data, "claims", "limitations", "alternative_explanations")
        return cls(tuple(map(str, data["claims"])), tuple(map(str, data["limitations"])), tuple(map(str, data["alternative_explanations"])))


@dataclass(frozen=True, slots=True)
class ChallengerAssessment:
    materiality: ChallengeMateriality
    reason: str
    required_effect: str
    evidence_ids: tuple[str, ...]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "ChallengerAssessment":
        _required(data, "materiality", "reason", "required_effect", "evidence_ids")
        return cls(ChallengeMateriality(str(data["materiality"])), str(data["reason"]), str(data["required_effect"]), tuple(map(str, data["evidence_ids"])))


class SemanticStages(Protocol):
    def triage(self, signal: CandidateSignal, evidence: tuple[Evidence, ...]) -> TriageDecision: ...
    def investigate(self, signal: CandidateSignal, evidence: tuple[Evidence, ...]) -> InvestigationAnalysis: ...
    def challenge(self, analysis: InvestigationAnalysis, evidence: tuple[Evidence, ...]) -> ChallengerAssessment: ...


@dataclass(slots=True)
class GoldenPathRun:
    run_id: str
    signal_id: str
    created_at: datetime
    execution_mode: str = "LIVE_WORLD_OBSERVATION"
    source_observation_mode: str = "CURRENT_REAL"
    original_execution_reference: str | None = None
    state: str = "SEMANTIC_TRIAGE_PENDING"
    audit: list[dict[str, Any]] = field(default_factory=list)
    triage: TriageDecision | None = None
    analysis: InvestigationAnalysis | None = None
    challenge: ChallengerAssessment | None = None
    disposition: StrategicDisposition | None = None
    disposition_factors: dict[str, bool] = field(default_factory=dict)
    reentry_condition: str | None = None

    def event(self, stage: str, detail: str, metadata: dict[str, Any] | None = None) -> None:
        item = {"stage": stage, "detail": detail, "at": self.created_at.isoformat()}
        if metadata is not None:
            item["metadata"] = metadata
        self.audit.append(item)

    def view_model(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id, "signal_id": self.signal_id, "state": self.state,
            "execution_mode": self.execution_mode,
            "source_observation_mode": self.source_observation_mode,
            "original_execution_reference": self.original_execution_reference,
            "triage": asdict(self.triage) if self.triage else None,
            "investigation": asdict(self.analysis) if self.analysis else None,
            "challenger": {**asdict(self.challenge), "materiality": self.challenge.materiality.value} if self.challenge else None,
            "disposition": self.disposition.value if self.disposition else None,
            "disposition_factors": self.disposition_factors,
            "reentry_condition": self.reentry_condition,
            "audit": self.audit,
        }


class GoldenPathOrchestrator:
    """One observation-led, bounded WP01 run; it never retries a semantic stage."""
    def __init__(self, stages: SemanticStages):
        self.stages = stages

    def run(self, signal: CandidateSignal, evidence: tuple[Evidence, ...], now: datetime,
            execution_id: str | None = None, execution_mode: str = "LIVE_WORLD_OBSERVATION",
            source_observation_mode: str = "CURRENT_REAL", original_execution_reference: str | None = None) -> GoldenPathRun:
        if not evidence or any(not item.content_hash for item in evidence):
            raise ValueError("golden path fails closed without hashed evidence")
        if len({item.investigation_id for item in evidence}) != 1:
            raise ValueError("golden path fails closed on cross-investigation evidence")
        run = GoldenPathRun(execution_id or "run-" + signal.signal_id, signal.signal_id, now,
                            execution_mode, source_observation_mode, original_execution_reference)
        run.event("observation.accepted", signal.provenance_reference)
        triage = self.stages.triage(signal, evidence)
        run.triage = triage
        if not triage.warrants_investigation:
            run.state = "TRIAGED_OUT"
            run.event("semantic_triage.completed", "not_warranted")
            return run
        run.state = "INVESTIGATING"
        run.event("semantic_triage.completed", "warranted", getattr(self.stages, "metrics", {}).get("Semantic Triage"))
        analysis = self.stages.investigate(signal, evidence)
        run.analysis = analysis
        run.state = "CHALLENGING"
        run.event("investigation.completed", "bounded_evidence_review", getattr(self.stages, "metrics", {}).get("Investigation"))
        challenge = self.stages.challenge(analysis, evidence)
        run.challenge = challenge
        run.event("challenger.completed", challenge.materiality.value, getattr(self.stages, "metrics", {}).get("Evidence Challenger"))
        investigation = Investigation(evidence[0].investigation_id, Initiator.FRIDA, now, InvestigationState.INVESTIGATING)
        for item in evidence:
            investigation.attach(item)
        if challenge.materiality is ChallengeMateriality.CRITICAL:
            investigation.challenges.append(Challenge("challenge-" + signal.signal_id, investigation.investigation_id, "wp01-emerging-claim", challenge.materiality, challenge.reason))
        governed = evaluate(list(evidence), challenge)
        # Critical challenges cannot be bypassed; all other outcomes are policy-owned.
        if challenge.materiality is ChallengeMateriality.CRITICAL:
            run.state = "STOPPED_CRITICAL_CHALLENGE"
            run.event("disposition.blocked", "critical_challenge")
            return run
        investigation.issue(governed.disposition)
        run.disposition = governed.disposition
        run.disposition_factors = governed.factors
        run.reentry_condition = governed.reentry_condition
        run.state = "COMPLETED"
        run.event("disposition.completed", governed.disposition.value)
        return run


def wp01_current_evidence(now: datetime) -> tuple[Evidence, ...]:
    """Bounded references only; no claim of point geometry or economic growth."""
    return (
        Evidence("wp01-s1-0525", "wp01", EvidenceClass.REAL, "DENUE", "denue_22_0525_csv.zip", now, now, "dc7d317aaf846cf4c58213fdf8d72f8635ade40fee0216a9a145580fa721e0e0", {"edition": "05/2025"}, GeographicConfidence.UNRESOLVED),
        Evidence("wp01-s1-0526", "wp01", EvidenceClass.REAL, "DENUE", "denue_22_0526_corrected_csv.zip", now, now, "2ea1e298086f109cdbdb6a036d6cd3ecfbdfe26123b34248d73b1d06c201304a", {"edition": "05/2026 corrected"}, GeographicConfidence.UNRESOLVED),
        Evidence("wp01-s2-felix", "wp01", EvidenceClass.REAL, "S2", "s2_implan_felix_osores_map.pdf", now, now, "72e2fff82fd181ee114f698b3c7c31716c8068363d3a8c9bfb4fb1a5108d64e0", {"use": "planning context"}, GeographicConfidence.AREA_CENTROID),
        Evidence("wp01-s3-semaforo", "wp01", EvidenceClass.REAL, "S3", "s3_puertas_de_san_miguel_stages_2026.csv", now, now, "1b7a624038ef54fcbad6848cde728725de5eb68328ba4d6c4895f2bdb1571acb", {"use": "published development records"}, GeographicConfidence.UNRESOLVED),
    )

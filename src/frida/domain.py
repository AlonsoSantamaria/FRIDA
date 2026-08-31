"""Frozen Golden Path v1.0 deterministic domain core (no model/runtime dependency)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

class EvidenceClass(StrEnum): REAL="REAL"; DERIVED="DERIVED"; SIMULATED="SIMULATED"
class GeographicConfidence(StrEnum): EXACT="EXACT"; INTERPOLATED="INTERPOLATED"; AREA_CENTROID="AREA_CENTROID"; UNRESOLVED="UNRESOLVED"
class Initiator(StrEnum): FRIDA="FRIDA"; HUMAN="HUMAN"
class ChallengeMateriality(StrEnum): ADVISORY="ADVISORY"; MATERIAL="MATERIAL"; CRITICAL="CRITICAL"
class StrategicDisposition(StrEnum): ESCALATE="ESCALATE"; KEEP_WATCHING="KEEP_WATCHING"; EVIDENCE_INSUFFICIENT="EVIDENCE_INSUFFICIENT"
class ExecutionStatus(StrEnum): COMPLETED="COMPLETED"; MODEL_FAILURE="MODEL_FAILURE"; RUNTIME_FAILURE="RUNTIME_FAILURE"; BUDGET_LIMIT_REACHED="BUDGET_LIMIT_REACHED"
class InvestigationState(StrEnum): NOTICED="NOTICED"; TRIAGED_OUT="TRIAGED_OUT"; INVESTIGATING="INVESTIGATING"; RECONSIDERING="RECONSIDERING"; COMPLETED="COMPLETED"

@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str; investigation_id: str; evidence_class: EvidenceClass; source_id: str
    source_reference: str; source_date: datetime | None; acquired_at: datetime; content_hash: str
    payload: dict[str, Any]; geographic_confidence: GeographicConfidence = GeographicConfidence.UNRESOLVED
    schema_version: str = "1.0"
    def __post_init__(self):
        if not self.content_hash: raise ValueError("evidence requires integrity hash")

@dataclass(frozen=True, slots=True)
class Challenge:
    challenge_id: str; investigation_id: str; target_claim_id: str; materiality: ChallengeMateriality
    reason: str; resolved: bool = False

@dataclass(slots=True)
class Investigation:
    investigation_id: str; initiator: Initiator; opened_at: datetime; state: InvestigationState = InvestigationState.NOTICED
    review_reason: str | None = None; evidence: list[Evidence] = field(default_factory=list); challenges: list[Challenge] = field(default_factory=list)
    execution_status: ExecutionStatus | None = None; strategic_disposition: StrategicDisposition | None = None; audit: list[str] = field(default_factory=list)
    def attach(self, item: Evidence) -> None:
        if item.investigation_id != self.investigation_id: raise ValueError("cross-investigation evidence")
        self.evidence.append(item); self.audit.append(f"evidence:{item.evidence_id}")
    def issue(self, disposition: StrategicDisposition) -> None:
        if any(c.materiality is ChallengeMateriality.CRITICAL and not c.resolved for c in self.challenges): raise ValueError("critical challenge blocks disposition")
        if disposition is StrategicDisposition.ESCALATE and any(e.geographic_confidence in {GeographicConfidence.AREA_CENTROID, GeographicConfidence.UNRESOLVED} for e in self.evidence): raise ValueError("insufficient geographic confidence for escalation")
        self.execution_status=ExecutionStatus.COMPLETED; self.strategic_disposition=disposition; self.state=InvestigationState.COMPLETED; self.audit.append(f"disposition:{disposition}")

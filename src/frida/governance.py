"""Deterministic disposition constraints; model reasoning may not bypass these rules."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from .domain import ChallengeMateriality, Evidence, GeographicConfidence, StrategicDisposition

@dataclass(frozen=True, slots=True)
class Evaluation:
    disposition: StrategicDisposition
    factors: dict[str, bool]
    reentry_condition: str | None

def evaluate(evidence: list[Evidence], challenger: Any | None = None) -> Evaluation:
    """Apply deterministic policy to governed evidence and Challenger state."""
    materiality = getattr(challenger, "materiality", None)
    challenger_material = materiality is ChallengeMateriality.MATERIAL
    challenger_critical = materiality is ChallengeMateriality.CRITICAL
    if not evidence:
        return Evaluation(StrategicDisposition.EVIDENCE_INSUFFICIENT,{
            "evidence_present": False, "geographic_precision": False,
            "challenger_material": challenger_material, "challenger_critical": challenger_critical,
        }, None)
    geographic_ok = all(x.geographic_confidence in {GeographicConfidence.EXACT, GeographicConfidence.INTERPOLATED} for x in evidence)
    if not geographic_ok:
        return Evaluation(StrategicDisposition.EVIDENCE_INSUFFICIENT,{
            "evidence_present": True, "geographic_precision": False,
            "challenger_material": challenger_material, "challenger_critical": challenger_critical,
        }, None)
    if challenger_material or challenger_critical:
        # Existing contract materiality is authoritative, whereas the free-text
        # required_effect is not a machine policy vocabulary.  Conservatively
        # require further governance evidence without letting model text issue policy.
        return Evaluation(StrategicDisposition.EVIDENCE_INSUFFICIENT, {
            "evidence_present": True, "geographic_precision": True,
            "challenger_material": challenger_material, "challenger_critical": challenger_critical,
        }, "CHALLENGER_GOVERNANCE_REVIEW")
    # Valid precision removes the blocker but does not fabricate urgency or causality.
    return Evaluation(StrategicDisposition.KEEP_WATCHING,{
        "evidence_present": True, "geographic_precision": True,
        "challenger_material": False, "challenger_critical": False,
    },"NEXT_APPROVED_SOURCE_EDITION")

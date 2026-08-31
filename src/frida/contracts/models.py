"""Provisional, dependency-free domain contracts.

These types are engineering probes for C2-C4. They preserve the proposed
semantics without selecting a database, validation framework, event bus,
agent runtime, or cloud service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class SourceStatus(StrEnum):
    LIVE_REAL = "LIVE_REAL"
    CONTROLLED_PUBLIC = "CONTROLLED_PUBLIC"
    SIMULATED_MUNICIPAL = "SIMULATED_MUNICIPAL"


class ClaimType(StrEnum):
    OBSERVATION = "OBSERVATION"
    INFERENCE = "INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    PROJECTION = "PROJECTION"
    RECOMMENDATION = "RECOMMENDATION"


class ClaimStatus(StrEnum):
    OPEN = "OPEN"
    SUPPORTED = "SUPPORTED"
    CONTESTED = "CONTESTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    RETIRED = "RETIRED"


class EvidenceRelation(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CONTEXTUALIZES = "CONTEXTUALIZES"


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    schema_version: str
    event_id: str
    event_type: str
    occurred_at: datetime
    correlation_id: str
    causation_id: str | None
    producer: str
    payload: dict[str, Any]
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    investigation_id: str
    source_name: str
    source_locator: str
    source_status: SourceStatus
    retrieved_at: datetime
    content_hash: str
    geography: str | None = None
    reliability_notes: str | None = None
    retrieval_method: str | None = None
    schema_version: str = "0.1"


@dataclass(frozen=True, slots=True)
class Claim:
    id: str
    investigation_id: str
    statement: str
    claim_type: ClaimType
    status: ClaimStatus
    created_by: str
    created_at: datetime
    confidence_factors: dict[str, float] = field(default_factory=dict)
    schema_version: str = "0.1"


@dataclass(frozen=True, slots=True)
class EvidenceClaimLink:
    evidence_id: str
    claim_id: str
    relation: EvidenceRelation
    strength: float
    rationale_ref: str | None = None
    schema_version: str = "0.1"

    def __post_init__(self) -> None:
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError("strength must be between 0.0 and 1.0")


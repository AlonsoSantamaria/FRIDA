"""Client-isolated governed memory for autonomously discovered public sources."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from urllib.parse import urlparse
from uuid import uuid4

LIFECYCLE = ("DISCOVERED", "SCREENED", "APPROVED", "SUSPENDED", "RETIRED")
AUTONOMOUS_CLASSES = {"OFFICIAL_GOVERNMENT", "STATUTORY_AGENCY", "PUBLIC_BODY", "OPEN_DATA", "RECOGNIZED_NEWS", "OFFICIAL_ANNOUNCEMENT", "INSTITUTIONAL"}
OPERABLE_NORMALIZERS = {
    "https://planningdata.london.gov.uk/",
    "https://environment.data.gov.uk/flood-monitoring/",
    "https://data.london.gov.uk/download/2zp76/q43/gla_2024_housing_led_central_msoa_la_level.xlsx",
    "https://data.london.gov.uk/download/exy3m/e4x/MPS%20Borough%20Level%20Crime%20(most%20recent%2024%20months).csv",
}


@dataclass(frozen=True)
class SourceProposal:
    source_name: str
    publisher: str
    canonical_url: str
    geographic_scope: str
    source_class: str
    strategic_domains: tuple[str, ...]
    why_proposed: str
    evidence_gap: str
    access_licensing_notes: str
    freshness_cadence: str
    normalization_method: str
    privacy_assessment: str
    reliability_assessment: str


def canonical_fingerprint(proposal: SourceProposal) -> str:
    return sha256(json.dumps(asdict(proposal), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def screen(proposal: SourceProposal) -> tuple[bool, str]:
    parsed = urlparse(proposal.canonical_url)
    if parsed.scheme != "https" or not parsed.netloc:
        return False, "URL_NOT_SECURE_OR_CANONICAL"
    if proposal.source_class not in AUTONOMOUS_CLASSES:
        return False, "UNSUPPORTED_SOURCE_CLASS"
    if not proposal.strategic_domains:
        return False, "NO_STRATEGIC_DOMAIN"
    if proposal.privacy_assessment.upper() not in {"AGGREGATE_ONLY", "NO_PERSONAL_DATA", "PUBLIC_INSTITUTIONAL"}:
        return False, "PRIVACY_REVIEW_REQUIRED"
    if proposal.reliability_assessment.upper() not in {"RELIABLE", "OFFICIAL", "RECOGNIZED"}:
        return False, "RELIABILITY_REVIEW_REQUIRED"
    if proposal.canonical_url not in OPERABLE_NORMALIZERS:
        return False, "SCREENED_REQUIRES_NORMALIZER"
    return True, "PREAUTHORIZED_PUBLIC_SOURCE_POLICY_v1"


class SourceRegistry:
    """Creates a proposal, then appends each deterministic lifecycle transition."""
    def __init__(self, store): self.store = store

    def remember(self, assignment_id: str, proposal: SourceProposal, *, operationally_validated: bool=False) -> dict[str, str]:
        if assignment_id != "LONDON_FINAL_ACTIVE":
            raise ValueError("source discovery is client-isolated to active London assignment")
        fingerprint = canonical_fingerprint(proposal)
        existing = self.store.source_registry_by_fingerprint(assignment_id, fingerprint)
        if existing:
            return {"source_registry_id": str(existing["source_registry_id"]), "status": str(existing["status"]), "outcome": "ALREADY_REMEMBERED"}
        source_id = "source-registry-" + uuid4().hex
        self.store.create_source_registry_entry(source_id, assignment_id, asdict(proposal), fingerprint)
        approved, reason = screen(proposal)
        self.store.append_source_registry_event(source_id, "SCREENED", reason)
        if approved and operationally_validated:
            self.store.set_source_registry_status(source_id, "APPROVED")
            self.store.append_source_registry_event(source_id, "APPROVED", reason)
            return {"source_registry_id": source_id, "status": "APPROVED", "outcome": reason}
        status = "SCREENED" if approved or reason == "SCREENED_REQUIRES_NORMALIZER" else "SUSPENDED"
        reason = "OPERATIONAL_VALIDATION_REQUIRED" if approved and not operationally_validated else reason
        self.store.set_source_registry_status(source_id, status)
        self.store.append_source_registry_event(source_id, status, reason)
        return {"source_registry_id": source_id, "status": status, "outcome": reason}

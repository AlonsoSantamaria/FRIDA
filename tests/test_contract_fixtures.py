from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from frida.contracts import (  # noqa: E402
    Claim,
    ClaimStatus,
    ClaimType,
    Evidence,
    EvidenceClaimLink,
    EvidenceRelation,
    EventEnvelope,
    SourceStatus,
)


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ContractFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture_path = PROJECT_ROOT / "tests" / "fixtures" / "contract_probe.json"
        cls.fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    def test_event_carries_causality_and_idempotency_metadata(self) -> None:
        data = self.fixture["event"]
        event = EventEnvelope(
            schema_version=data["schema_version"],
            event_id=data["event_id"],
            event_type=data["event_type"],
            occurred_at=parse_timestamp(data["occurred_at"]),
            correlation_id=data["correlation_id"],
            causation_id=data["causation_id"],
            producer=data["producer"],
            payload=data["payload"],
            idempotency_key=data["idempotency_key"],
        )
        self.assertTrue(event.idempotency_key)
        self.assertEqual(event.schema_version, "0.1")

    def test_source_status_survives_fixture_loading(self) -> None:
        statuses = {
            SourceStatus(item["source_status"])
            for item in self.fixture["evidence"]
        }
        self.assertEqual(
            statuses,
            {SourceStatus.CONTROLLED_PUBLIC, SourceStatus.SIMULATED_MUNICIPAL},
        )

    def test_claim_can_have_supporting_and_contradictory_evidence(self) -> None:
        claim_data = self.fixture["claim"]
        claim = Claim(
            id=claim_data["id"],
            investigation_id=claim_data["investigation_id"],
            statement=claim_data["statement"],
            claim_type=ClaimType(claim_data["claim_type"]),
            status=ClaimStatus(claim_data["status"]),
            created_by=claim_data["created_by"],
            created_at=parse_timestamp(claim_data["created_at"]),
            confidence_factors=claim_data["confidence_factors"],
        )
        links = [
            EvidenceClaimLink(
                evidence_id=item["evidence_id"],
                claim_id=item["claim_id"],
                relation=EvidenceRelation(item["relation"]),
                strength=item["strength"],
            )
            for item in self.fixture["links"]
        ]
        self.assertEqual(claim.status, ClaimStatus.CONTESTED)
        self.assertEqual(
            {link.relation for link in links},
            {EvidenceRelation.SUPPORTS, EvidenceRelation.CONTRADICTS},
        )

    def test_link_strength_rejects_out_of_range_values(self) -> None:
        with self.assertRaises(ValueError):
            EvidenceClaimLink(
                evidence_id="evidence-001",
                claim_id="claim-001",
                relation=EvidenceRelation.SUPPORTS,
                strength=1.1,
            )

    def test_evidence_requires_explicit_source_status(self) -> None:
        data = self.fixture["evidence"][0]
        evidence = Evidence(
            id=data["id"],
            investigation_id=data["investigation_id"],
            source_name=data["source_name"],
            source_locator=data["source_locator"],
            source_status=SourceStatus(data["source_status"]),
            retrieved_at=parse_timestamp(data["retrieved_at"]),
            content_hash=data["content_hash"],
        )
        self.assertEqual(evidence.source_status, SourceStatus.CONTROLLED_PUBLIC)


if __name__ == "__main__":
    unittest.main()


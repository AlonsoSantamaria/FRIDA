from datetime import UTC, datetime
import unittest

from frida.domain import ChallengeMateriality, Evidence, EvidenceClass, GeographicConfidence, StrategicDisposition
from frida.golden_path import ChallengerAssessment
from frida.governance import evaluate


def precise_evidence():
    return [Evidence("e", "wp01", EvidenceClass.REAL, "source", "ref", datetime.now(UTC), datetime.now(UTC), "hash", {}, GeographicConfidence.EXACT)]


class ChallengerGovernanceTests(unittest.TestCase):
    def test_material_challenger_constrains_otherwise_keep_watching_policy(self):
        advisory = ChallengerAssessment(ChallengeMateriality.ADVISORY, "r", "note", ("e",))
        material = ChallengerAssessment(ChallengeMateriality.MATERIAL, "r", "downgrade", ("e",))
        self.assertEqual(evaluate(precise_evidence(), advisory).disposition, StrategicDisposition.KEEP_WATCHING)
        result = evaluate(precise_evidence(), material)
        self.assertEqual(result.disposition, StrategicDisposition.EVIDENCE_INSUFFICIENT)
        self.assertTrue(result.factors["challenger_material"])
        self.assertEqual(result.reentry_condition, "CHALLENGER_GOVERNANCE_REVIEW")

    def test_challenger_never_directly_selects_disposition(self):
        critical = ChallengerAssessment(ChallengeMateriality.CRITICAL, "r", "stop", ("e",))
        result = evaluate(precise_evidence(), critical)
        self.assertEqual(result.disposition, StrategicDisposition.EVIDENCE_INSUFFICIENT)
        self.assertTrue(result.factors["challenger_critical"])

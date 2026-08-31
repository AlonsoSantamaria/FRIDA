from datetime import datetime, UTC
import unittest
from frida.domain import Evidence, EvidenceClass, GeographicConfidence, StrategicDisposition
from frida.governance import evaluate
T=datetime(2026,8,23,tzinfo=UTC)
def item(geo): return Evidence("e","wp01",EvidenceClass.REAL,"S3","official",T,T,"sha256:e",{},geo)
class WP01GovernanceTests(unittest.TestCase):
 def test_current_unresolved_geography_is_insufficient(self):
  result=evaluate([item(GeographicConfidence.UNRESOLVED)]); self.assertEqual(result.disposition,StrategicDisposition.EVIDENCE_INSUFFICIENT); self.assertFalse(result.factors["geographic_precision"])
 def test_valid_evidence_mutation_changes_evaluated_factors_and_outcome(self):
  current=evaluate([item(GeographicConfidence.UNRESOLVED)]); mutated=evaluate([item(GeographicConfidence.EXACT)])
  self.assertNotEqual(current.disposition,mutated.disposition); self.assertNotEqual(current.factors,mutated.factors); self.assertEqual(mutated.reentry_condition,"NEXT_APPROVED_SOURCE_EDITION")
 def test_area_centroid_cannot_support_precise_result(self): self.assertEqual(evaluate([item(GeographicConfidence.AREA_CENTROID)]).disposition,StrategicDisposition.EVIDENCE_INSUFFICIENT)

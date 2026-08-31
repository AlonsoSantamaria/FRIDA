from datetime import datetime, UTC
import unittest
from frida.domain import *

NOW=datetime(2026,8,23,tzinfo=UTC)
def evidence(i, geo=GeographicConfidence.UNRESOLVED): return Evidence(i,"wp01",EvidenceClass.REAL,"S3","official",NOW,NOW,"sha256:x",{},geo)
class GoldenPathDomainTests(unittest.TestCase):
 def test_wp01_can_issue_insufficient_without_geometry(self):
  x=Investigation("wp01",Initiator.FRIDA,NOW); x.attach(evidence("e1")); x.issue(StrategicDisposition.EVIDENCE_INSUFFICIENT); self.assertEqual(x.strategic_disposition,StrategicDisposition.EVIDENCE_INSUFFICIENT)
 def test_critical_challenge_blocks_escalation(self):
  x=Investigation("wp01",Initiator.FRIDA,NOW); x.attach(evidence("e1",GeographicConfidence.EXACT)); x.challenges.append(Challenge("c","wp01","claim",ChallengeMateriality.CRITICAL,"gap"));
  with self.assertRaises(ValueError): x.issue(StrategicDisposition.ESCALATE)
 def test_failure_never_issues_disposition(self):
  x=Investigation("wp01",Initiator.FRIDA,NOW); x.execution_status=ExecutionStatus.MODEL_FAILURE; self.assertIsNone(x.strategic_disposition)

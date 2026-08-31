from datetime import datetime, UTC
import unittest
from frida.domain import EvidenceClass, Initiator, InvestigationState
from frida.observation import DenueObserver, SemaforoObserver, ReplaySnapshot, open_approved_fixture_investigation, validate_and_prepare
T=datetime(2026,8,23,tzinfo=UTC)
def snapshot(source, hash="h", cls=EvidenceClass.REAL): return ReplaySnapshot(source,"official://"+source,T,hash,cls,1,T)
class Gate5LocalPreparationTests(unittest.TestCase):
 def test_two_sources_share_pending_triage_boundary(self):
  for observer, source in ((DenueObserver(),"DENUE"),(SemaforoObserver(),"SEMAFORO")):
   result=validate_and_prepare(observer,snapshot(source)); self.assertTrue(result.triage_pending); self.assertEqual(result.candidate_signal.source_id,source); self.assertEqual(result.audit[-1].event_type,"semantic_triage.pending")
 def test_duplicate_has_no_candidate_or_side_effect(self):
  observer=DenueObserver(); validate_and_prepare(observer,snapshot("DENUE")); result=validate_and_prepare(observer,snapshot("DENUE")); self.assertIsNone(result.candidate_signal); self.assertEqual(result.filtered_reason,"duplicate")
 def test_deterministic_invalid_source_is_filtered_without_triage(self):
  result=validate_and_prepare(DenueObserver(),snapshot("DENUE",cls=EvidenceClass.SIMULATED)); self.assertFalse(result.triage_pending); self.assertEqual(result.filtered_reason,"unsupported_observer_source")
 def test_only_explicit_approved_fixture_opens_locally(self):
  signal=validate_and_prepare(DenueObserver(),snapshot("DENUE")).candidate_signal; investigation=open_approved_fixture_investigation(signal,T); self.assertEqual(investigation.initiator,Initiator.FRIDA); self.assertEqual(investigation.state,InvestigationState.INVESTIGATING)

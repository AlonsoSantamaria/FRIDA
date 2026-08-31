from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from frida.controlled_replay_run import execute, HISTORICAL_CANDIDATE
from frida.persistence import StagingStore
from frida.observation import CandidateSignal
from frida.golden_path import TriageDecision, InvestigationAnalysis, ChallengerAssessment
from frida.domain import ChallengeMateriality

NOW=datetime(2026,8,24,tzinfo=UTC)
class FakeNative:
 def triage(self,*a): return TriageDecision(False,'r',('wp01-s1-0526',),('u',)),{'finish_reason':'STOP','usage':{}}
 def investigation(self,*a): raise AssertionError('unreachable')
 def challenger(self,*a): raise AssertionError('unreachable')
class BrokenInvestigation(FakeNative):
 def triage(self,*a): return TriageDecision(True,'r',('wp01-s1-0526',),('u',)),{'finish_reason':'STOP','usage':{}}
 def investigation(self,*a): raise ValueError('invalid investigation')
class CompleteNative(FakeNative):
 def triage(self,*a): return TriageDecision(True,'r',('wp01-s1-0526',),('u',)),{'finish_reason':'STOP','usage':{}}
 def investigation(self,*a): return InvestigationAnalysis(('c',),('l',),('a',)),{'finish_reason':'STOP','usage':{}}
 def challenger(self,*a): return ChallengerAssessment(ChallengeMateriality.MATERIAL,'r','downgrade',('wp01-s1-0526',)),{'finish_reason':'STOP','usage':{}}
class NativeEntrypointTests(unittest.TestCase):
 def test_real_entrypoint_uses_persisted_gate_before_downstream(self):
  with TemporaryDirectory() as d:
   db=Path(d)/'x.sqlite3'; store=StagingStore(db); store.record_candidate(CandidateSignal(HISTORICAL_CANDIDATE,'DENUE','2ea1e298086f109cdbdb6a036d6cd3ecfbdfe26123b34248d73b1d06c201304a',NOW,'k','official',2)); store.close()
   root=Path(__file__).resolve().parents[1]
   with patch('frida.controlled_replay_run.NativeStages',FakeNative): result=execute(str(db),str(root),'test',NOW)
   self.assertEqual(result['state'],'GOVERNANCE_STOPPED')
   check=StagingStore(db); rows=check.connection.execute("select event_type from execution_events order by event_id").fetchall(); check.close()
   names=[r[0] for r in rows]; self.assertIn('stage.gate_blocked',names); self.assertNotIn('stage.started',names[3:])
 def test_investigation_failure_stops_before_challenger(self):
  with TemporaryDirectory() as d:
   db=Path(d)/'x.sqlite3'; s=StagingStore(db); s.record_candidate(CandidateSignal(HISTORICAL_CANDIDATE,'DENUE','2ea1e298086f109cdbdb6a036d6cd3ecfbdfe26123b34248d73b1d06c201304a',NOW,'k2','official',2)); s.close()
   with patch('frida.controlled_replay_run.NativeStages',BrokenInvestigation):
    with self.assertRaises(ValueError): execute(str(db),str(Path(__file__).resolve().parents[1]),'test',NOW)
   s=StagingStore(db); names=[r[0] for r in s.connection.execute("select event_type from execution_events order by event_id").fetchall()]; s.close()
   self.assertIn('stage.runtime_failed',names); self.assertNotIn('disposition.completed',names)
 def test_completed_entrypoint_projects_persisted_semantic_artifacts(self):
  with TemporaryDirectory() as d:
   db=Path(d)/'x.sqlite3'; s=StagingStore(db); s.record_candidate(CandidateSignal(HISTORICAL_CANDIDATE,'DENUE','2ea1e298086f109cdbdb6a036d6cd3ecfbdfe26123b34248d73b1d06c201304a',NOW,'k3','official',2)); s.close()
   with patch('frida.controlled_replay_run.NativeStages',CompleteNative): result=execute(str(db),str(Path(__file__).resolve().parents[1]),'test',NOW)
   self.assertEqual(result['disposition'],'EVIDENCE_INSUFFICIENT')
   self.assertEqual(result['triage']['reason'],'r')
   self.assertEqual(result['investigation']['evidence_ids'][0],'wp01-s1-0525')
   self.assertEqual(result['challenger']['materiality'],'MATERIAL')
   names=[item['stage'] for item in result['audit']]
   self.assertLess(names.index('stage.semantic_artifact_persisted'),names.index('stage.gate_opened'))

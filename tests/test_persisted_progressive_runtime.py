import unittest
from frida.persisted_progressive_runtime import PersistedProgressiveRuntime
from frida.golden_path import TriageDecision, InvestigationAnalysis, ChallengerAssessment
from frida.domain import ChallengeMateriality

class Store:
 def __init__(self): self.events=[]
 def append_execution_event(self,*args): self.events.append(args[2:])
class Stages:
 def __init__(self, triage): self.triage_value=triage; self.calls=[]
 def triage(self,*a): self.calls.append('triage'); return self.triage_value, {'finish_reason':'STOP','usage':{}}
 def investigation(self,*a): self.calls.append('investigation'); return InvestigationAnalysis(('c',),('l',),('a',)), {'finish_reason':'STOP','usage':{}}
 def challenger(self,*a): self.calls.append('challenger'); return ChallengerAssessment(ChallengeMateriality.MATERIAL,'r','x',('e',)), {'finish_reason':'STOP','usage':{}}
class Tests(unittest.TestCase):
 def test_false_triage_persists_gate_before_stop(self):
  store=Store(); stages=Stages(TriageDecision(False,'r',('e',),('u',)))
  PersistedProgressiveRuntime(store,'x',stages).run(None,())
  self.assertEqual(stages.calls,['triage']); self.assertIn('stage.gate_blocked',[e[0] for e in store.events])

 def test_artifact_is_persisted_before_its_gate_and_downstream_stage(self):
  store=Store(); stages=Stages(TriageDecision(True,'r',('e',),('u',)))
  PersistedProgressiveRuntime(store,'x',stages).run(None,())
  names=[e[0] for e in store.events]
  triage_artifact=names.index('stage.semantic_artifact_persisted')
  triage_gate=names.index('stage.gate_opened')
  investigation_started=names.index('stage.started', triage_gate + 1)
  self.assertLess(triage_artifact,triage_gate)
  self.assertLess(triage_gate,investigation_started)
  artifact=store.events[triage_artifact][1]['artifact']
  self.assertEqual(artifact['relevant_evidence_ids'],('e',))

 def test_artifact_persistence_failure_blocks_investigation(self):
  class FailingStore(Store):
   def append_execution_event(self,*args):
    if args[2]=='stage.semantic_artifact_persisted': raise OSError('ledger unavailable')
    super().append_execution_event(*args)
  store=FailingStore(); stages=Stages(TriageDecision(True,'r',('e',),('u',)))
  with self.assertRaises(OSError): PersistedProgressiveRuntime(store,'x',stages).run(None,())
  self.assertEqual(stages.calls,['triage'])

 def test_challenger_critical_artifact_blocks_disposition(self):
  class CriticalStages(Stages):
   def challenger(self,*a):
    self.calls.append('challenger')
    return ChallengerAssessment(ChallengeMateriality.CRITICAL,'r','x',('e',)), {'finish_reason':'STOP','usage':{}}
  store=Store(); stages=CriticalStages(TriageDecision(True,'r',('e',),('u',)))
  self.assertIsNone(PersistedProgressiveRuntime(store,'x',stages).run(None,()))
  names=[e[0] for e in store.events]
  self.assertIn('stage.semantic_artifact_persisted',names)
  self.assertIn('disposition.blocked',names)
  self.assertNotIn('disposition.completed',names)
 def test_valid_path_is_three_and_gated(self):
  store=Store(); stages=Stages(TriageDecision(True,'r',('e',),('u',)))
  PersistedProgressiveRuntime(store,'x',stages).run(None,())
  self.assertEqual(stages.calls,['triage','investigation','challenger']); self.assertEqual([e[0] for e in store.events].count('stage.gate_opened'),3)

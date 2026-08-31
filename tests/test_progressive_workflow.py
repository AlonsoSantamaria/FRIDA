import unittest
from frida.golden_path import TriageDecision, InvestigationAnalysis, ChallengerAssessment
from frida.domain import ChallengeMateriality
from frida.progressive_workflow import run_progressive, VERIFY_CAP

class ProgressiveWorkflowTests(unittest.TestCase):
 def test_false_triage_stops_once(self):
  calls=[]
  def t(): calls.append('t'); return ({}, {})
  result=run_progressive(t, lambda _: TriageDecision(False,'r',('e',),('u',)), lambda: (_ for _ in ()).throw(AssertionError()), lambda x:x, lambda: (_ for _ in ()).throw(AssertionError()), lambda x:x)
  self.assertEqual(calls,['t']); self.assertEqual(result.total_semantic_requests,1); self.assertEqual(result.retry_count,0)
 def test_valid_path_has_three_once(self):
  def call(v): return lambda: (v, {'usage':{'total_token_count':1},'finish_reason':'STOP'})
  result=run_progressive(call({}), lambda _: TriageDecision(True,'r',('e',),('u',)), call({}), lambda _: InvestigationAnalysis(('c',),('l',),('a',)), call({}), lambda _: ChallengerAssessment(ChallengeMateriality.MATERIAL,'r','x',('e',)))
  self.assertEqual(result.total_semantic_requests,3); self.assertEqual(result.total_usage['total_token_count'],3)
  self.assertTrue(all(e.configured_max_output_tokens==VERIFY_CAP for e in result.events))

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from frida.persistence import StagingStore
from frida.strategic_briefing import StrategicBriefingService, DISCLOSURE, HISTORICAL_BRIEF_CUTOFFS

class FakeStages:
 def advisory_foresight(self,bundle,allowed): return ({"trajectory":"A plausible capacity trajectory.","possible_implications":["Implication"],"leading_indicators":["Indicator"],"intervention_window":"Bounded window","opportunity_window":"Bounded opportunity","what_would_change_the_view":["More evidence"],"next_observation_plan":["Observe"],"evidence_ids_used":list(allowed),"uncertainties":["No causation"]},{"usage":{},"latency_ms":1})
 def executive_brief(self,bundle,allowed): return ({"executive_summary":"A bounded London attention hypothesis is available.","what_deserves_attention":["Capacity context"],"why_it_may_matter":"Evidence supports a question, not a conclusion.","remaining_uncertainty":["No causal claim"],"what_frida_will_watch_next":["Planning progression"],"evidence_ids_used":list(allowed)},{"usage":{},"latency_ms":1})
 def close(self): pass

class StrategicBriefingTests(unittest.TestCase):
 def test_current_brief_is_durable_and_not_canonical_attention(self):
  with TemporaryDirectory() as d:
   s=StagingStore(str(Path(d)/'f.sqlite3')); s.append_first_appraisal('a','LONDON_FINAL_ACTIVE',{'input_fingerprint_sha256':'x'},'VALIDATED',{'strategic_interest':'POSSIBLE','evidence_ids_used':['e1']},{})
   service=StrategicBriefingService(s,FakeStages()); ident,_,brief,_=service.create_current(); saved=s.strategic_briefs()
   self.assertEqual(saved[0]['brief_id'],ident); self.assertEqual(brief['semantic_status'],'ADVISORY_YELLOW_NOT_CANONICAL_ATTENTION'); self.assertEqual(brief['evidence_scope_disclosure'],DISCLOSURE)
   self.assertEqual(brief['executive_posture'],'YELLOW')
   s.close()

 def test_additional_historical_cutoffs_are_real_and_cutoff_enforced(self):
  self.assertEqual(HISTORICAL_BRIEF_CUTOFFS, {date(2018,10,25), date(2026,8,27), date(2026,8,29)})
  with TemporaryDirectory() as d:
   s=StagingStore(str(Path(d)/'f.sqlite3')); service=StrategicBriefingService(s,FakeStages())
   ident,_,brief,meta=service.create_historical(date(2018,10,25)); saved=s.strategic_briefs()[0]
   self.assertEqual(ident, saved['brief_id']); self.assertEqual(saved['historical_as_of'], '2018-10-25')
   self.assertEqual(brief['executive_posture'], 'GREEN')
   self.assertEqual(brief['semantic_status'], 'HISTORICAL_EVIDENCE_CUTOFF_NO_CANONICAL_ATTENTION')
   self.assertTrue(saved['runtime_meta']['cutoff_enforced_before_model']); self.assertEqual(len(saved['evidence_ids']), 2)
   service.close(); s.close()

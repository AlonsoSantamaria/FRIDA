import unittest
from frida.foresight_ingestion import build_scenario_input_set,SOURCE_STATE_ID
from frida.foresight_workflow import ForesightController,ForesightGovernance,water_resilience_results,water_resilience_scenarios,stress_bounds,judge_projection
from frida.native_stage_runtime import ForesightNativeStages,NativeStages
FACTS=[{"fact_id":f"FW-OBS-00{i}","observation_status":"OBSERVED"} for i in range(1,6)]
class ForesightWorkflowTests(unittest.TestCase):
 def setUp(self): self.events=[]; self.results=water_resilience_results(water_resilience_scenarios(build_scenario_input_set(SOURCE_STATE_ID),FACTS),FACTS)
 def ctl(self,fail=None,materiality="ADVISORY"):
  def v(x,s):
   if s==fail: raise ValueError(s)
   return x
  return ForesightController(lambda n,p:self.events.append(n),lambda:{"assessment":"valid"},lambda x:{"materiality":materiality,"qualifications":["q"]},v)
 def test_variants_are_qualitative_and_governed(self): self.assertEqual([x.projected_label for x in self.results],["BASELINE_CONSTRAINT","ELEVATED_CONSTRAINT","MITIGATION_REVIEW_CONSTRAINT"])
 def test_eligibility_and_authorization_fail_closed(self): self.assertEqual(self.ctl().run(False,True,self.results)[1],"eligibility"); self.assertEqual(self.ctl().run(True,False,self.results)[1],"human_authorization")
 def test_invalid_foresight_blocks_challenger(self): self.assertEqual(self.ctl("foresight").run(True,True,self.results)[1],"foresight_validation"); self.assertNotIn("foresight.challenge_artifact_persisted",self.events)
 def test_invalid_challenger_blocks_governance(self): self.assertEqual(self.ctl("challenger").run(True,True,self.results)[1],"challenger_validation"); self.assertNotIn("foresight.governance_persisted",self.events)
 def test_material_and_critical_effects(self): self.assertEqual(self.ctl(materiality="MATERIAL").run(True,True,self.results)[0],ForesightGovernance.RESTRICTED); self.assertEqual(self.ctl(materiality="CRITICAL").run(True,True,self.results)[0],ForesightGovernance.BLOCKED)
 def test_native_specialist_contract_is_bounded_and_tool_free(self): self.assertEqual(ForesightNativeStages(NativeStages(client=object())).policy(),{"tools":[],"runtime_calls_max":2,"retries":0,"prose_fallback":False,"governance":"deterministic"})
 def test_stress_bounds_are_qualitative_and_preserve_restricted_status(self): self.assertEqual(stress_bounds()["prospective_governance"],"RESTRICTED"); self.assertNotIn("number",str(stress_bounds()).lower())
 def test_judge_projection_exposes_governed_chain_without_reasoning(self):
  p=judge_projection(FACTS,build_scenario_input_set(SOURCE_STATE_ID)["assumptions"],self.results,{"materiality":"MATERIAL","reason":"r","required_effect":"e"},ForesightGovernance.RESTRICTED); self.assertEqual(p["governance"],"RESTRICTED"); self.assertEqual(p["challenger"]["materiality"],"MATERIAL")

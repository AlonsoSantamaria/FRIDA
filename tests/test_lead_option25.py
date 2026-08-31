from __future__ import annotations

import unittest
from datetime import UTC, datetime

from frida.domain import ChallengeMateriality
from frida.golden_path import ChallengerAssessment, InvestigationAnalysis, wp01_current_evidence
from frida.lead_catalogue import AGENT_CATALOGUE
from frida.lead_runtime import LeadRuntime, TOTAL_CALL_LIMIT
from frida.observation import CandidateSignal


class _Store:
    def __init__(self): self.events=[]
    def append_execution_event(self, execution_id, at, name, payload): self.events.append((name, payload))
    def persist_execution_initial_plan(self, execution_id, plan): self.events.append(("execution.initial_plan_persisted", plan))


class _Stages:
    def __init__(self, attention): self.attention_value=attention; self.called=[]
    def _meta(self): return {"usage": {}, "latency_ms": 1, "configured_max_output_tokens": 4096}
    def lead_attention(self,*_): self.called.append("attention"); return self.attention_value, self._meta()
    def economic_directory_change(self,*_): self.called.append("economic"); return InvestigationAnalysis(("directory change",),("not economic growth",),("edition correction",)),self._meta()
    def urban_development_status(self,*_): self.called.append("urban"); return InvestigationAnalysis(("status context",),("no point precision",),("publication lag",)),self._meta()
    def lead_review(self,*_): self.called.append("review"); return {"decision":"READY_FOR_CHALLENGE","reason":"bounded evidence sufficient","reduced_claim_scope":[],"evidence_gap":None,"additional_specialist":None,"mandate":None},self._meta()
    def challenger(self,*_): self.called.append("challenger"); return ChallengerAssessment(ChallengeMateriality.ADVISORY,"limits retained","preserve limitations",("wp01-s1-0526",)),self._meta()
    def lead_interpretation(self,*_): self.called.append("interpretation"); return {"decision":"RESTRICT_INTERPRETATION","supported_interpretation":["directory change only"],"removed_or_restricted_claims":["economic growth"],"unresolved_uncertainties":["geographic precision"]},self._meta()


class LeadOption25Tests(unittest.TestCase):
    def setUp(self):
        self.evidence=wp01_current_evidence(datetime.now(tz=UTC))
        self.signal=CandidateSignal("historical-signal","DENUE","a"*64,datetime.now(tz=UTC),"dedup","source",0)
        self.plan={"attention":"INVESTIGATE","reason":"change merits bounded review","relevant_evidence_ids":["wp01-s1-0526"],"uncertainties":["directory-only"],"strategic_dimension":"urban economic signal","investigation_question":"What can be supported?","claim_scope":["directory difference"],"evidence_gaps":["point precision"],"selected_specialists":["economic_directory_change","urban_development_status"],"mandates":["interpret editions","interpret status"]}

    def test_catalogue_is_logical_and_bounded(self):
        self.assertEqual(set(AGENT_CATALOGUE), {"frida_lead","economic_directory_change","urban_development_status","independent_challenger"})
        self.assertEqual(AGENT_CATALOGUE["frida_lead"]["tools"], [])

    def test_watch_never_creates_candidate_or_dispatches(self):
        plan={**self.plan,"attention":"WATCH","investigation_question":None,"selected_specialists":[],"mandates":[]}
        stages=_Stages(plan); store=_Store(); result=LeadRuntime(store,"x",stages).run(self.signal,self.evidence)
        self.assertEqual(result["state"],"SIGNAL_WATCH")
        self.assertEqual(stages.called,["attention"])
        self.assertFalse(any(name=="candidate.historical_reference_authorized" for name,_ in store.events))

    def test_investigate_is_lead_owned_and_gated(self):
        stages=_Stages(self.plan); store=_Store(); result=LeadRuntime(store,"x",stages).run(self.signal,self.evidence)
        self.assertEqual(result["state"],"COMPLETED")
        self.assertEqual(stages.called,["attention","economic","urban","review","challenger","interpretation"])
        names=[name for name,_ in store.events]
        self.assertLess(names.index("stage.gate_opened"), names.index("stage.started", names.index("stage.gate_opened")+1))
        self.assertLessEqual(6,TOTAL_CALL_LIMIT)

    def test_invalid_plan_physically_blocks_specialists(self):
        plan={**self.plan,"mandates":[]}; stages=_Stages(plan); store=_Store()
        # Adapter validation normally catches this; runtime gate is defensive too.
        result=LeadRuntime(store,"x",stages).run(self.signal,self.evidence)
        self.assertEqual(result["state"],"STOPPED_INVALID_PLAN")
        self.assertEqual(stages.called,["attention"])

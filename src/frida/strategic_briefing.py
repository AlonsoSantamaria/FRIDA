"""Bounded non-authorizing Foresight and durable Executive Brief artifacts."""
from __future__ import annotations
from datetime import date
from typing import Any
from uuid import uuid4
from .native_stage_runtime import NativeStages
from .london_time_travel import SEQUENCE

DISCLOSURE = "This brief reflects the authorized public sources currently available to FRIDA. Broader, higher-resolution and more timely authorized sources may materially improve the precision and completeness of the assessment."

# The submission sample uses only these non-redundant, real Time Travel
# cutoffs: a planning milestone, TfL context, then environmental context.
HISTORICAL_BRIEF_CUTOFFS = frozenset({
    date(2018, 10, 25),
    date(2026, 8, 27),
    date(2026, 8, 29),
})

class StrategicBriefingService:
    def __init__(self, store: Any, stages: NativeStages | None = None): self.store,self.stages=store,stages or NativeStages()
    def create_current(self, assignment_id="LONDON_FINAL_ACTIVE"):
        advisories=self.store.london_advisories(assignment_id)
        if not advisories: raise ValueError("no persisted advisory evidence available")
        advisory=next((a for a in advisories if a["result"].get("strategic_interest")=="POSSIBLE"), advisories[0])
        evidence=list(advisory["result"].get("evidence_ids_used",[]))
        posture="YELLOW" if advisory["result"].get("strategic_interest")=="POSSIBLE" else "GREEN"
        bundle={"assignment_id":assignment_id,"advisory_record_id":advisory["record_id"],"advisory":advisory["result"],"executive_posture_fixed_by_governance":posture,"evidence_scope_disclosure":DISCLOSURE,"external_developments":[]}
        foresight,fmeta=self.stages.advisory_foresight(bundle,set(evidence))
        brief,bmeta=self.stages.executive_brief({**bundle,"foresight":foresight},set(evidence))
        brief={**brief,"executive_posture":posture,"semantic_status":"ADVISORY_YELLOW_NOT_CANONICAL_ATTENTION","evidence_scope_disclosure":DISCLOSURE,"external_developments":[]}
        identifier="brief-"+uuid4().hex
        self.store.append_strategic_brief(identifier,assignment_id,"ATTENTION_BRIEF","VALIDATED",evidence,foresight,brief,{"agents":["Advisory Foresight","Executive Briefing"],"foresight":fmeta,"briefing":bmeta,"retries":0})
        return identifier,foresight,brief,{"foresight":fmeta,"briefing":bmeta}
    def close(self): self.stages.close()
    def create_historical(self, cutoff):
        """Strictly cutoff-filtered historical brief; no current fabric enters."""
        existing=next((item for item in self.store.strategic_briefs() if str(item.get("historical_as_of") or "").startswith(cutoff.isoformat())),None)
        if existing:
            return existing["brief_id"],existing["foresight"],existing["brief"],existing["runtime_meta"]
        visible=[step for step in SEQUENCE if step.source_date.date() <= cutoff]
        if not visible: raise ValueError("no London evidence at historical cutoff")
        evidence=["historical-"+step.content_hash[:20] for step in visible]
        facts=[{"evidence_id":eid,"source_id":step.source_id,"source_date":step.source_date.isoformat(),"facts":step.facts} for eid,step in zip(evidence,visible)]
        bundle={"assignment_id":"LONDON_FINAL_ACTIVE","historical_evidence_cutoff":cutoff.isoformat(),"facts":facts,"evidence_scope_disclosure":DISCLOSURE,"external_developments":[]}
        foresight,fmeta=self.stages.advisory_foresight(bundle,set(evidence))
        brief,bmeta=self.stages.executive_brief({**bundle,"executive_posture_fixed_by_governance":"GREEN","foresight":foresight},set(evidence))
        brief={**brief,"executive_posture":"GREEN","semantic_status":"HISTORICAL_EVIDENCE_CUTOFF_NO_CANONICAL_ATTENTION","evidence_scope_disclosure":DISCLOSURE,"external_developments":[]}
        identifier="historical-brief-"+uuid4().hex
        self.store.append_strategic_brief(identifier,"LONDON_FINAL_ACTIVE","HISTORICAL_TIME_TRAVEL_BRIEF","VALIDATED",evidence,foresight,brief,{"agents":["Advisory Foresight","Executive Briefing"],"foresight":fmeta,"briefing":bmeta,"retries":0,"cutoff_enforced_before_model":True},cutoff.isoformat())
        return identifier,foresight,brief,{"foresight":fmeta,"briefing":bmeta}

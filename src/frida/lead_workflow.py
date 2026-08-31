"""Bounded Lead-first state machine; runtime adapters are injected and governed."""
from __future__ import annotations
from dataclasses import dataclass, field
from .lead_catalogue import ALLOWED_SPECIALISTS

@dataclass
class LeadCase:
    signal_id:str; events:list[tuple[str,dict]]=field(default_factory=list); calls:int=0; candidate_created:bool=False
    def event(self,name,payload): self.events.append((name,payload))

def run_lead_case(signal_id, attention, specialist, review, challenger, interpretation):
    """At most 8 injected calls; all outputs must already be validated by adapters."""
    case=LeadCase(signal_id); plan=attention(); case.calls+=1; case.event("frida.attention_result",plan)
    if plan["attention"] != "INVESTIGATE": case.event("signal.retained",{"state":plan["attention"]}); return case
    selected=plan["selected_specialists"]
    if not selected or set(selected).difference(ALLOWED_SPECIALISTS): raise ValueError("Lead selected unauthorized specialist")
    case.candidate_created=True; case.event("candidate.created",{"signal_id":signal_id}); case.event("frida.investigation_plan_created",plan)
    artifacts=[]
    for name in selected:
        artifacts.append(specialist(name,plan)); case.calls+=1; case.event("specialist.artifact_validated",{"agent":name})
    decision=review(artifacts,plan); case.calls+=1; case.event("frida.evidence_reviewed",decision)
    if decision["decision"] == "STOP": return case
    if decision["decision"] == "REQUEST_ADDITIONAL_SPECIALIST":
        name=decision["additional_specialist"]
        if name not in ALLOWED_SPECIALISTS or len(artifacts)>=3: raise ValueError("additional specialist is unauthorized or exceeds bound")
        artifacts.append(specialist(name,decision)); case.calls+=1; case.event("frida.additional_specialist_selected",{"agent":name})
    if case.calls>=7: raise ValueError("model-call bound prevents challenger")
    challenge=challenger(artifacts); case.calls+=1; case.event("challenger.completed",challenge)
    final=interpretation(artifacts,challenge); case.calls+=1; case.event("frida.interpretation",final)
    if case.calls>8: raise ValueError("model-call bound exceeded")
    case.event("governance.ready",{"lead_decision":final["decision"]}); return case

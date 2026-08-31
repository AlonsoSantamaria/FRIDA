"""Frozen Foresight branch: deterministic, ledger-first, and runtime-inert."""
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

class InputClass(StrEnum):
    OBSERVED="OBSERVED"; ASSUMED="ASSUMED"; SIMULATED="SIMULATED"; PROJECTED="PROJECTED"
class ForesightGovernance(StrEnum):
    BRIEFING_ELIGIBLE="BRIEFING_ELIGIBLE"; RESTRICTED="RESTRICTED"; BLOCKED="BLOCKED"
STRESS_BOUNDS_VERSION="FORESIGHT-WR-2201-STRESS-BOUNDS-v1"
STRESS_FAILURE_CONDITIONS=(
 "STOP_STRESS_INTERPRETATION if any required observed fact loses hash/provenance validity.",
 "STOP_STRESS_INTERPRETATION if additional pressure is presented as OBSERVED rather than its declared ASSUMED condition.",
 "STOP_STRESS_INTERPRETATION if the interpretation requires demand magnitude, operational failure, probability, municipal supply condition, or mitigation effectiveness.",
)
@dataclass(frozen=True, slots=True)
class ScenarioDefinition: scenario_definition_id:str; variant:str; parent_id:str|None; assumption_ids:tuple[str,...]
@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario_result_id:str; scenario_definition_id:str; computation_mode:str; projected_label:str; observed_evidence_ids:tuple[str,...]; assumed_ids:tuple[str,...]; limitations:tuple[str,...]
def water_resilience_scenarios(input_set:dict[str,Any], facts:list[dict[str,str]])->tuple[ScenarioDefinition,...]:
    if input_set.get("computation_mode")!="QUALITATIVE": raise ValueError("only frozen qualitative scenario is supported")
    ids={x["assumption_id"] for x in input_set["assumptions"]}
    if not {"ASM-WR-BASELINE-001","ASM-WR-STRESS-001","ASM-WR-MITIGATION-001"}.issubset(ids) or not all(x.get("observation_status")=="OBSERVED" for x in facts): raise ValueError("governed Foresight inputs invalid")
    return (ScenarioDefinition("SCN-WR-BASELINE-v1","BASELINE",None,("ASM-WR-BASELINE-001",)),ScenarioDefinition("SCN-WR-STRESS-v1","STRESS","SCN-WR-BASELINE-v1",("ASM-WR-BASELINE-001","ASM-WR-STRESS-001")),ScenarioDefinition("SCN-WR-MITIGATION-v1","MITIGATION","SCN-WR-BASELINE-v1",("ASM-WR-BASELINE-001","ASM-WR-MITIGATION-001")))
def water_resilience_results(defs:tuple[ScenarioDefinition,...], facts:list[dict[str,str]])->tuple[ScenarioResult,...]:
    labels={"BASELINE":"BASELINE_CONSTRAINT","STRESS":"ELEVATED_CONSTRAINT","MITIGATION":"MITIGATION_REVIEW_CONSTRAINT"}; observed=tuple(x["fact_id"] for x in facts); limitation=("No numeric future water demand, extraction, recharge, deficit, probability, supply condition, or mitigation magnitude is produced.",)
    return tuple(ScenarioResult("RES-"+x.variant+"-v1",x.scenario_definition_id,"QUALITATIVE",labels[x.variant],observed,x.assumption_ids,limitation) for x in defs)
def govern(challenge:dict[str,Any], prerequisites:bool)->tuple[ForesightGovernance,tuple[str,...]]:
    if not prerequisites or challenge.get("materiality")=="CRITICAL": return ForesightGovernance.BLOCKED,("GOVERNANCE_PREREQUISITE_OR_CRITICAL_CHALLENGE",)
    if challenge.get("materiality")=="MATERIAL": return ForesightGovernance.RESTRICTED,tuple(challenge.get("qualifications",()))
    return ForesightGovernance.BRIEFING_ELIGIBLE,()
def stress_bounds() -> dict[str,object]:
    """Versioned qualitative guardrail; it prevents overreach, not false precision."""
    return {"contract_id":STRESS_BOUNDS_VERSION,"classification":"ASSUMED","conditions":STRESS_FAILURE_CONDITIONS,"prospective_governance":"RESTRICTED","unrestricted_requires":"separately governed operational parameters/evidence"}
def judge_projection(observed:list[dict[str,str]], assumptions:list[dict[str,object]], results:tuple[ScenarioResult,...], challenge:dict[str,object], outcome:ForesightGovernance)->dict[str,object]:
    return {"observed_evidence":[x["fact_id"] for x in observed],"assumptions":[x["assumption_id"] for x in assumptions],"projected_variants":[{"variant":x.scenario_definition_id,"label":x.projected_label,"limitations":x.limitations} for x in results],"challenger":{"materiality":challenge["materiality"],"reason":challenge["reason"],"required_effect":challenge["required_effect"]},"governance":outcome.value,"stress_bounds":stress_bounds()}
class ForesightController:
    def __init__(self,ledger:Callable[[str,dict[str,Any]],None],foresight:Callable[[],dict[str,Any]],challenger:Callable[[dict[str,Any]],dict[str,Any]],validate:Callable[[dict[str,Any],str],dict[str,Any]]): self.ledger,self.foresight,self.challenger,self.validate=ledger,foresight,challenger,validate
    def run(self,eligible:bool,authorized:bool,results:tuple[ScenarioResult,...])->tuple[ForesightGovernance|None,str]:
        if not eligible: self.ledger("foresight.stopped",{"stop_point":"eligibility","retry_count":0}); return None,"eligibility"
        if not authorized: self.ledger("foresight.stopped",{"stop_point":"human_authorization","retry_count":0}); return None,"human_authorization"
        self.ledger("foresight.started",{"result_ids":[x.scenario_result_id for x in results]})
        try: artifact=self.validate(self.foresight(),"foresight")
        except Exception: self.ledger("foresight.stopped",{"stop_point":"foresight_validation","retry_count":0}); return None,"foresight_validation"
        self.ledger("foresight.artifact_persisted",artifact); self.ledger("foresight.gate_opened",{})
        try: challenge=self.validate(self.challenger(artifact),"challenger")
        except Exception: self.ledger("foresight.stopped",{"stop_point":"challenger_validation","retry_count":0}); return None,"challenger_validation"
        self.ledger("foresight.challenge_artifact_persisted",challenge); self.ledger("foresight.challenger_gate_opened",{})
        outcome,quals=govern(challenge,True); self.ledger("foresight.governance_persisted",{"outcome":outcome.value,"qualifications":list(quals)}); return outcome,"completed"

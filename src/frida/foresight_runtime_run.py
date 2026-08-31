"""One-shot Foresight runtime entrypoint; invoked only with explicit clearance."""
from __future__ import annotations
import csv, json, uuid
from dataclasses import asdict
from pathlib import Path
from .foresight_ingestion import SOURCE_STATE_ID,SCENARIO_INPUT_SET_ID,build_scenario_input_set,evaluate_eligibility
from .foresight_workflow import water_resilience_scenarios,water_resilience_results,govern
from .native_stage_runtime import NativeStages,ForesightNativeStages
from .persistence import StagingStore

def execute(database='data/frida-foresight.sqlite3',root='data/foresight-evidence/water-resilience-v1'):
 store=StagingStore(database); state=store.foresight_source_state(SOURCE_STATE_ID); input_set=build_scenario_input_set(SOURCE_STATE_ID); decision=evaluate_eligibility(state,input_set)
 if decision['status']!='ELIGIBLE': return {'status':'BLOCKED','reason':'eligibility'}
 facts=list(csv.DictReader((Path(root)/'normalized/observed_facts_v1.csv').open(encoding='utf-8'))); defs=water_resilience_scenarios(input_set,facts); results=water_resilience_results(defs,facts)
 eid='foresight-verify-'+uuid.uuid4().hex; store.create_foresight_execution(eid,SOURCE_STATE_ID,SCENARIO_INPUT_SET_ID,'FORESIGHT_RUNTIME_VERIFICATION_CLEARANCE_2026-08-25')
 event=lambda name,payload:store.append_foresight_event(eid,name,payload)
 event('foresight.authorization_verified',{'role':'FORESIGHT_INITIATION_APPROVER','authorization':'accepted'}); event('foresight.scenarios_persisted',{'definitions':[x.scenario_definition_id for x in defs],'results':[x.scenario_result_id for x in results]})
 native=NativeStages(); stages=ForesightNativeStages(native); evidence={x['fact_id'] for x in facts}; assumptions={x['assumption_id'] for x in input_set['assumptions']}; result_ids={x.scenario_result_id for x in results}; definition_ids={x.scenario_definition_id for x in defs}
 payload={'input_set':input_set,'scenario_definitions':[asdict(x) for x in defs],'scenario_results':[asdict(x) for x in results],'facts':facts}
 try:
  assessment,meta=stages.assessment(payload,evidence,assumptions,result_ids); event('foresight.model_completed',meta); event('foresight.artifact_persisted',assessment); event('foresight.gate_opened',{})
  challenge,meta2=stages.challenge({'assessment':assessment,'results':[asdict(x) for x in results]},evidence,assumptions,definition_ids,result_ids); event('foresight.challenger_model_completed',meta2); event('foresight.challenge_artifact_persisted',challenge); event('foresight.challenger_gate_opened',{})
  outcome,quals=govern(challenge,True); event('foresight.governance_persisted',{'outcome':outcome.value,'qualifications':list(quals)}); return {'status':'VERIFIED','execution_id':eid,'assessment':assessment,'assessment_meta':meta,'challenge':challenge,'challenge_meta':meta2,'governance':outcome.value,'events':store.connection.execute('select event_type,payload_json from foresight_execution_events where foresight_execution_id=? order by event_id',(eid,)).fetchall()}
 except Exception as error:
  event('foresight.stopped',{'error_class':type(error).__name__,'retry_count':0}); return {'status':'BLOCKED','execution_id':eid,'error_class':type(error).__name__}
 finally: native.close(); store.close()

"""Real native structured-output adapter, inert until an authorized call."""
from __future__ import annotations
import os, time
from dataclasses import asdict
from typing import Any
from .adk_runtime import MODEL, LOCATION, _evidence_digest
from .semantic_completion import (parse_native_triage, parse_native_investigation, parse_native_challenger,
    parse_native_lead_attention, parse_native_lead_review, parse_native_lead_interpretation,
    TriageCompletion, InvestigationCompletion, ChallengerCompletion,
    LeadAttentionPlanCompletion, LeadReviewCompletion, LeadInterpretationCompletion)

CAP = 4096
FIRST_APPRAISAL_OUTPUT_CAP = 6000
FIRST_APPRAISAL_TOTAL_HARD_CAP = 10000
class NativeStageError(RuntimeError):
 def __init__(self, stage, code, meta): super().__init__(code); self.stage,self.code,self.meta=stage,code,meta

class NativeStages:
 """One execution-scoped native client shared by its bounded semantic stages."""
 def __init__(self, project: str | None=None, client: Any | None=None, client_factory: Any | None=None):
  self.project=project or os.environ.get('GOOGLE_CLOUD_PROJECT')
  self._client=client
  self._client_factory=client_factory
  self._closed=False

 def _get_client(self):
  if self._closed:
   raise NativeStageError('Workflow','CLIENT_LIFECYCLE_CLOSED',{})
  if self._client is None:
   if self._client_factory is not None:
    self._client=self._client_factory()
   else:
    from google import genai
    # Keep a strong reference for the whole bounded execution.  Creating the
    # client inline below allowed its finalizer to close the HTTP client before
    # ``generate_content`` finished using it.
    self._client=genai.Client(vertexai=True,project=self.project,location=LOCATION)
  return self._client

 def close(self) -> None:
  """Release the execution-scoped client only after the controller stops."""
  if self._closed:
   return
  self._closed=True
  close=getattr(self._client,'close',None)
  if callable(close):
   close()

 def _invoke(self, stage, schema, prompt, payload, parser, allowed, output_cap=CAP, total_hard_cap=None):
  from google.genai import types
  if os.environ.get('GOOGLE_GENAI_USE_VERTEXAI')!='TRUE' or os.environ.get('GOOGLE_CLOUD_LOCATION')!=LOCATION: raise NativeStageError(stage,'RUNTIME_CONFIGURATION_UNAVAILABLE',{})
  started=time.monotonic(); response=self._get_client().models.generate_content(model=MODEL,contents=str(payload),config=types.GenerateContentConfig(system_instruction=prompt,response_mime_type='application/json',response_schema=schema,temperature=0,max_output_tokens=output_cap))
  candidate=response.candidates[0] if response.candidates else None; usage=getattr(response,'usage_metadata',None); meta={'finish_reason':str(getattr(candidate,'finish_reason',None)),'usage':usage.model_dump(exclude_none=True) if usage else {},'latency_ms':round((time.monotonic()-started)*1000),'model':MODEL,'configured_max_output_tokens':output_cap}
  if total_hard_cap is not None and int(meta['usage'].get('total_token_count', 0)) > total_hard_cap: raise NativeStageError(stage,'TOTAL_TOKEN_HARD_CAP_EXCEEDED',meta)
  if response.parsed is None: raise NativeStageError(stage,'MODEL_OUTPUT_INCOMPLETE',meta)
  try: return parser(response.parsed,allowed),meta
  except Exception as e: raise NativeStageError(stage,'STRUCTURED_RESULT_INVALID',meta) from e
 def triage(self, signal, evidence): return self._invoke('Semantic Triage',TriageCompletion,"You are FRIDA's Semantic Triage specialist. Use only approved evidence. Return only schema JSON.",{'signal':asdict(signal),'evidence':_evidence_digest(evidence)},parse_native_triage,{x.evidence_id for x in evidence})
 def investigation(self, signal, evidence): return self._invoke('Investigation',InvestigationCompletion,"You are FRIDA's Investigation specialist. Use only approved evidence. Return only schema JSON.",{'signal':asdict(signal),'evidence':_evidence_digest(evidence)},parse_native_investigation,{x.evidence_id for x in evidence})
 def challenger(self, analysis, evidence): return self._invoke('Independent Challenger',ChallengerCompletion,"You are FRIDA's Independent Challenger specialist. Use only approved evidence. Return only schema JSON.",{'investigation':asdict(analysis),'evidence':_evidence_digest(evidence)},parse_native_challenger,{x.evidence_id for x in evidence})
 def lead_attention(self, signal, evidence): return self._invoke('FRIDA Attention & Initial Plan',LeadAttentionPlanCompletion,"You are FRIDA, the bounded Lead Agent. Assess only the governed signal and evidence. Return IGNORE, WATCH, or INVESTIGATE. For INVESTIGATE provide one bounded question, approved specialists and matching mandates. Never issue final disposition. Return only schema JSON.",{'signal':asdict(signal),'evidence':_evidence_digest(evidence)},parse_native_lead_attention,{x.evidence_id for x in evidence})
 def economic_directory_change(self, signal, evidence, mandate): return self._invoke('Economic Directory Change',InvestigationCompletion,"You are FRIDA's Economic Directory Change specialist. Interpret DENUE edition evidence conservatively. Directory differences are not economic growth, openings, or closures without independent support. Follow the Lead mandate. Return only schema JSON.",{'signal':asdict(signal),'mandate':mandate,'evidence':_evidence_digest(evidence)},parse_native_investigation,{x.evidence_id for x in evidence})
 def urban_development_status(self, signal, evidence, mandate): return self._invoke('Urban Development Status',InvestigationCompletion,"You are FRIDA's Urban Development Status specialist. Interpret only approved development-status evidence and its geographic limits. Follow the Lead mandate. Return only schema JSON.",{'signal':asdict(signal),'mandate':mandate,'evidence':_evidence_digest(evidence)},parse_native_investigation,{x.evidence_id for x in evidence})
 def lead_review(self, plan, artifacts, evidence): return self._invoke('FRIDA Evidence Review',LeadReviewCompletion,"You are FRIDA, the bounded Lead Agent. Review validated specialist artifacts against the plan. Choose STOP, READY_FOR_CHALLENGE, or one bounded additional specialist. Do not issue final disposition. Return only schema JSON.",{'plan':plan,'artifacts':artifacts,'evidence':_evidence_digest(evidence)},parse_native_lead_review,{x.evidence_id for x in evidence})
 def lead_interpretation(self, artifacts, challenge, evidence): return self._invoke('FRIDA Post-Challenge Interpretation',LeadInterpretationCompletion,"You are FRIDA, the bounded Lead Agent. Interpret the challenged evidence conservatively. You may restrict interpretation; you may not issue final disposition. Return only schema JSON.",{'artifacts':artifacts,'challenge':asdict(challenge),'evidence':_evidence_digest(evidence)},parse_native_lead_interpretation,{x.evidence_id for x in evidence})
 def first_appraisal(self, bundle, allowed_evidence_ids):
  from .semantic_completion import FirstAppraisalCompletion, parse_native_first_appraisal
  prompt=("You are FRIDA's First Appraisal specialist. Consider only the approved normalized London evidence bundle. "
          "You may identify a possible strategic question, opportunity, problem, intervention opportunity and missing context. "
          "Do not create a Signal, Candidate, Case, severity, causal claim, recommendation, or final decision. "
          "Use only listed evidence IDs and only allow-listed context request names. Return only schema JSON.")
  return self._invoke('First Appraisal',FirstAppraisalCompletion,prompt,bundle,parse_native_first_appraisal,set(allowed_evidence_ids),FIRST_APPRAISAL_OUTPUT_CAP,FIRST_APPRAISAL_TOTAL_HARD_CAP)
 def enriched_appraisal(self, bundle, allowed_evidence_ids):
  from .semantic_completion import EnrichedAppraisalCompletion, parse_native_enriched_appraisal
  prompt=("You are FRIDA's bounded research synthesis specialist. Compare only the approved London planning, TfL, Environment Agency, and GLA housing-led projection context with the stated hypothesis. "
          "Identify whether the hypothesis becomes stronger, weaker or unchanged and whether a non-authorizing Yellow/Watch interpretation is better justified. "
          "Do not create a Signal, Candidate, Case, Red condition, causal claim, recommendation or final decision. "
          "Use only listed evidence IDs and only allow-listed context request names. Return only schema JSON.")
  return self._invoke('Bounded Research Appraisal',EnrichedAppraisalCompletion,prompt,bundle,parse_native_enriched_appraisal,set(allowed_evidence_ids))
 def advisory_foresight(self, bundle, allowed_evidence_ids):
  from .semantic_completion import AdvisoryForesightCompletion, parse_advisory_foresight
  prompt=("You are FRIDA's bounded Foresight agent. Consider only the persisted London advisory evidence. "
          "Describe plausible trajectories and indicators, not predictions or causal claims. Never create a Signal, Candidate, Case, Red, recommendation, or autonomous action. Return only schema JSON.")
  return self._invoke('Advisory Foresight', AdvisoryForesightCompletion, prompt, bundle, parse_advisory_foresight, set(allowed_evidence_ids), 4096, 10000)
 def executive_brief(self, bundle, allowed_evidence_ids):
  from .semantic_completion import ExecutiveBriefCompletion, parse_executive_brief
  prompt=("You are FRIDA's Executive Briefing agent. Produce a concise attributable strategic brief using only the supplied London evidence and foresight. "
          "The executive posture is fixed by deterministic governance and is not yours to choose. Respect the supplied advisory status; do not upgrade it to canonical Attention, Signal, Candidate, Case or Red. No certainty, causal claim, or government action. Return only schema JSON.")
  return self._invoke('Executive Briefing', ExecutiveBriefCompletion, prompt, bundle, parse_executive_brief, set(allowed_evidence_ids), 4096, 10000)

class ForesightNativeStages:
 """Future bounded native adapters; construction is inert and no runtime is invoked here."""
 def __init__(self, stages: NativeStages): self.stages=stages
 def assessment_contract(self):
  from .semantic_completion import ForesightAssessmentCompletion
  return ForesightAssessmentCompletion
 def challenge_contract(self):
  from .semantic_completion import ForesightChallengeAssessmentCompletion
  return ForesightChallengeAssessmentCompletion
 def assessment(self,payload,allowed_evidence,allowed_assumptions,allowed_results):
  from .semantic_completion import ForesightAssessmentCompletion,parse_native_foresight
  return self.stages._invoke('Foresight',ForesightAssessmentCompletion,"You are FRIDA's Foresight specialist. Interpret only governed qualitative ScenarioResults. Return only schema JSON.",payload,lambda result,_:parse_native_foresight(result,allowed_evidence,allowed_assumptions,allowed_results),allowed_evidence)
 def challenge(self,payload,allowed_evidence,allowed_assumptions,allowed_definitions,allowed_results):
  from .semantic_completion import ForesightChallengeAssessmentCompletion,parse_native_foresight_challenge
  return self.stages._invoke('Independent Challenger',ForesightChallengeAssessmentCompletion,"You are FRIDA's Independent Challenger for Foresight. Challenge only governed inputs. Return only schema JSON.",payload,lambda result,_:parse_native_foresight_challenge(result,allowed_evidence,allowed_assumptions,allowed_definitions,allowed_results),allowed_evidence)
 def policy(self): return {"tools":[],"runtime_calls_max":2,"retries":0,"prose_fallback":False,"governance":"deterministic"}

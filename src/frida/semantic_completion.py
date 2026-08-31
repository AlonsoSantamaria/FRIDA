"""Strict deterministic boundary for provider-facing task completion.

The provider only completes an ADK task with ``result_json: string``.  The
authoritative FRIDA result contracts are validated here, after that string has
been decoded, never delegated to provider tool-argument coercion.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, ValidationError

from .domain import ChallengeMateriality
from .golden_path import ChallengerAssessment, InvestigationAnalysis, TriageDecision


class CompletionEnvelope(BaseModel):
    """The deliberately small, provider-facing ADK task-completion contract."""
    model_config = ConfigDict(strict=True, extra="forbid")
    result_json: StrictStr


class _StrictStageResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class TriageCompletion(_StrictStageResult):
    warrants_investigation: StrictBool
    reason: StrictStr
    relevant_evidence_ids: list[StrictStr] = Field(min_length=1)
    uncertainties: list[StrictStr] = Field(min_length=1)


class InvestigationCompletion(_StrictStageResult):
    claims: list[StrictStr] = Field(min_length=1)
    limitations: list[StrictStr] = Field(min_length=1)
    alternative_explanations: list[StrictStr] = Field(min_length=1)


class ChallengerCompletion(_StrictStageResult):
    materiality: Literal["ADVISORY", "MATERIAL", "CRITICAL"]
    reason: StrictStr
    required_effect: StrictStr
    evidence_ids: list[StrictStr] = Field(min_length=1)

class LeadAttentionPlanCompletion(_StrictStageResult):
    attention: Literal["IGNORE", "WATCH", "INVESTIGATE"]
    reason: StrictStr
    relevant_evidence_ids: list[StrictStr] = Field(min_length=1)
    uncertainties: list[StrictStr] = Field(min_length=1)
    strategic_dimension: StrictStr
    investigation_question: StrictStr | None = None
    claim_scope: list[StrictStr] = Field(default_factory=list)
    evidence_gaps: list[StrictStr] = Field(default_factory=list)
    selected_specialists: list[Literal["economic_directory_change", "urban_development_status"]] = Field(default_factory=list)
    mandates: list[StrictStr] = Field(default_factory=list)

class LeadReviewCompletion(_StrictStageResult):
    decision: Literal["STOP", "READY_FOR_CHALLENGE", "REQUEST_ADDITIONAL_SPECIALIST"]
    reason: StrictStr
    reduced_claim_scope: list[StrictStr] = Field(default_factory=list)
    evidence_gap: StrictStr | None = None
    additional_specialist: Literal["economic_directory_change", "urban_development_status"] | None = None
    mandate: StrictStr | None = None

class LeadInterpretationCompletion(_StrictStageResult):
    decision: Literal["READY_FOR_GOVERNANCE", "RESTRICT_INTERPRETATION"]
    supported_interpretation: list[StrictStr] = Field(min_length=1)
    removed_or_restricted_claims: list[StrictStr] = Field(default_factory=list)
    unresolved_uncertainties: list[StrictStr] = Field(min_length=1)


class FirstAppraisalCompletion(_StrictStageResult):
    """Bounded curiosity artifact. It is deliberately not an authorization."""
    strategic_interest: Literal["NONE", "POSSIBLE"]
    opportunity_family: Literal["PROBLEM", "OPPORTUNITY", "INTERVENTION_OPPORTUNITY", "UNKNOWN"]
    strategic_question: StrictStr = Field(max_length=480)
    why_it_might_matter: StrictStr = Field(max_length=720)
    evidence_ids_used: list[StrictStr] = Field(min_length=1, max_length=8)
    missing_evidence: list[StrictStr] = Field(max_length=6)
    allowed_context_requests: list[Literal["LONDON_TFL_VICTORIA", "LONDON_PLANNING_SW8", "LONDON_EA_THAMES_TIDEWAY", "LONDON_GLA_HOUSING_LED_SW8", "LONDON_MPS_BOROUGH_SAFETY_SW8"]] = Field(max_length=3)
    uncertainties: list[StrictStr] = Field(min_length=1, max_length=6)
    research_warranted: StrictBool


class EnrichedAppraisalCompletion(_StrictStageResult):
    """Research synthesis; its Yellow assessment is advisory, never canonical Attention."""
    strategic_interest: Literal["NONE", "POSSIBLE"]
    opportunity_family: Literal["PROBLEM", "OPPORTUNITY", "INTERVENTION_OPPORTUNITY", "UNKNOWN"]
    hypothesis_direction: Literal["STRENGTHENED", "WEAKENED", "UNCHANGED"]
    watch_interpretation: Literal["NOT_JUSTIFIED", "BETTER_JUSTIFIED"]
    strategic_question: StrictStr = Field(max_length=480)
    how_evidence_changes_hypothesis: StrictStr = Field(max_length=720)
    evidence_ids_used: list[StrictStr] = Field(min_length=1, max_length=8)
    missing_evidence: list[StrictStr] = Field(max_length=6)
    allowed_context_requests: list[Literal["LONDON_TFL_VICTORIA", "LONDON_PLANNING_SW8", "LONDON_EA_THAMES_TIDEWAY", "LONDON_GLA_HOUSING_LED_SW8", "LONDON_MPS_BOROUGH_SAFETY_SW8"]] = Field(max_length=3)
    uncertainties: list[StrictStr] = Field(min_length=1, max_length=6)
    further_research_has_positive_information_value: StrictBool


class AdvisoryForesightCompletion(_StrictStageResult):
    """Non-predictive outlook over a persisted advisory evidence bundle."""
    trajectory: StrictStr = Field(max_length=520)
    possible_implications: list[StrictStr] = Field(min_length=1, max_length=5)
    leading_indicators: list[StrictStr] = Field(min_length=1, max_length=5)
    intervention_window: StrictStr = Field(max_length=360)
    opportunity_window: StrictStr = Field(max_length=360)
    what_would_change_the_view: list[StrictStr] = Field(min_length=1, max_length=5)
    next_observation_plan: list[StrictStr] = Field(min_length=1, max_length=5)
    evidence_ids_used: list[StrictStr] = Field(min_length=1, max_length=10)
    uncertainties: list[StrictStr] = Field(min_length=1, max_length=6)


class ExecutiveBriefCompletion(_StrictStageResult):
    executive_summary: StrictStr = Field(max_length=900)
    what_deserves_attention: list[StrictStr] = Field(max_length=5)
    why_it_may_matter: StrictStr = Field(max_length=720)
    remaining_uncertainty: list[StrictStr] = Field(min_length=1, max_length=6)
    what_frida_will_watch_next: list[StrictStr] = Field(min_length=1, max_length=5)
    evidence_ids_used: list[StrictStr] = Field(min_length=1, max_length=10)


class SourceDiscoveryCompletion(_StrictStageResult):
    """A proposal only; deterministic policy decides if it may be observed."""
    source_name: StrictStr = Field(max_length=160)
    publisher: StrictStr = Field(max_length=160)
    canonical_url: StrictStr = Field(max_length=1000)
    geographic_scope: StrictStr = Field(max_length=240)
    source_class: Literal["OFFICIAL_GOVERNMENT", "STATUTORY_AGENCY", "PUBLIC_BODY", "OPEN_DATA", "RECOGNIZED_NEWS", "OFFICIAL_ANNOUNCEMENT", "INSTITUTIONAL"]
    strategic_domains: list[StrictStr] = Field(min_length=1, max_length=5)
    why_proposed: StrictStr = Field(max_length=480)
    evidence_gap: StrictStr = Field(max_length=360)
    access_licensing_notes: StrictStr = Field(max_length=360)
    freshness_cadence: StrictStr = Field(max_length=120)
    normalization_method: StrictStr = Field(max_length=240)
    privacy_assessment: Literal["AGGREGATE_ONLY", "NO_PERSONAL_DATA", "PUBLIC_INSTITUTIONAL"]
    reliability_assessment: Literal["RELIABLE", "OFFICIAL", "RECOGNIZED"]


def _lead_attention_rules(value: dict[str, Any]) -> None:
    investigating = value["attention"] == "INVESTIGATE"
    planned = bool(value["selected_specialists"])
    if investigating and (not value["investigation_question"] or not planned or len(value["mandates"]) != len(value["selected_specialists"])):
        raise SemanticCompletionValidationError("INVESTIGATE requires a bounded question, specialists, and matching mandates")
    if not investigating and (value["investigation_question"] or planned or value["mandates"]):
        raise SemanticCompletionValidationError("IGNORE/WATCH may not authorize investigation work")


def _lead_review_rules(value: dict[str, Any]) -> None:
    additional = value["decision"] == "REQUEST_ADDITIONAL_SPECIALIST"
    if additional != bool(value["additional_specialist"] and value["mandate"]):
        raise SemanticCompletionValidationError("lead review additional-specialist decision is incomplete")


def parse_native_lead_attention(result: object, allowed_evidence_ids: set[str]) -> dict[str, Any]:
    value = _native_validated(result, LeadAttentionPlanCompletion).model_dump()
    _allow_only(value["relevant_evidence_ids"], allowed_evidence_ids)
    _lead_attention_rules(value)
    return value


def parse_native_lead_review(result: object, allowed_evidence_ids: set[str]) -> dict[str, Any]:
    value = _native_validated(result, LeadReviewCompletion).model_dump()
    _allow_only([], allowed_evidence_ids)
    _lead_review_rules(value)
    return value


def parse_native_lead_interpretation(result: object, allowed_evidence_ids: set[str]) -> dict[str, Any]:
    value = _native_validated(result, LeadInterpretationCompletion).model_dump()
    _allow_only([], allowed_evidence_ids)
    return value


def parse_native_first_appraisal(result: object, allowed_evidence_ids: set[str]) -> dict[str, Any]:
    value = _native_validated(result, FirstAppraisalCompletion).model_dump()
    _allow_only(value["evidence_ids_used"], allowed_evidence_ids)
    if value["research_warranted"] and (not value["missing_evidence"] or not value["allowed_context_requests"]):
        raise SemanticCompletionValidationError("research requires explicit missing evidence and an allow-listed context request")
    if value["strategic_interest"] == "NONE" and value["research_warranted"]:
        raise SemanticCompletionValidationError("non-interest may not warrant research")
    return value


def parse_native_enriched_appraisal(result: object, allowed_evidence_ids: set[str]) -> dict[str, Any]:
    value = _native_validated(result, EnrichedAppraisalCompletion).model_dump()
    _allow_only(value["evidence_ids_used"], allowed_evidence_ids)
    if value["watch_interpretation"] == "BETTER_JUSTIFIED" and value["strategic_interest"] != "POSSIBLE":
        raise SemanticCompletionValidationError("a stronger Watch interpretation requires possible strategic interest")
    return value


def parse_advisory_foresight(result: object, allowed_evidence_ids: set[str]) -> dict[str, Any]:
    value = _native_validated(result, AdvisoryForesightCompletion).model_dump()
    _allow_only(value["evidence_ids_used"], allowed_evidence_ids)
    return value


def parse_executive_brief(result: object, allowed_evidence_ids: set[str]) -> dict[str, Any]:
    value = _native_validated(result, ExecutiveBriefCompletion).model_dump()
    _allow_only(value["evidence_ids_used"], allowed_evidence_ids)
    return value


def parse_source_discovery(result: object) -> dict[str, Any]:
    return _native_validated(result, SourceDiscoveryCompletion).model_dump()


class ForesightAssessmentCompletion(_StrictStageResult):
    scenario_input_set_id: StrictStr
    scenario_result_ids: list[StrictStr] = Field(min_length=1)
    strategic_implications: list[StrictStr] = Field(min_length=1)
    decision_relevant_differences: list[StrictStr] = Field(min_length=1)
    sensitivity_factors: list[StrictStr] = Field(min_length=1)
    limitations: list[StrictStr] = Field(min_length=1)
    uncertainties: list[StrictStr] = Field(min_length=1)
    evidence_ids: list[StrictStr] = Field(min_length=1)
    assumption_ids: list[StrictStr] = Field(min_length=1)
    horizon_label: StrictStr


class ForesightChallengeAssessmentCompletion(_StrictStageResult):
    scenario_input_set_id: StrictStr
    scenario_definition_ids: list[StrictStr] = Field(min_length=1)
    scenario_result_ids: list[StrictStr] = Field(min_length=1)
    assumption_ids: list[StrictStr]
    evidence_ids: list[StrictStr] = Field(min_length=1)
    materiality: Literal["ADVISORY", "MATERIAL", "CRITICAL"]
    reason: StrictStr
    required_effect: StrictStr
    qualifications: list[StrictStr] = Field(min_length=1)


class SemanticCompletionValidationError(ValueError):
    """A fail-closed parsing or authoritative-schema boundary failure."""


def _native_validated(result: object, model: type[_StrictStageResult]) -> _StrictStageResult:
    """Strictly validate provider-native parsed output without an envelope."""
    try:
        if isinstance(result, BaseModel):
            result = result.model_dump()
        return model.model_validate(result)
    except ValidationError as error:
        raise SemanticCompletionValidationError("native semantic result violates its authoritative schema") from error


def _decoded_object(result: object) -> dict[str, Any]:
    """Accept only an exact envelope containing a JSON object string."""
    try:
        envelope = CompletionEnvelope.model_validate(result)
    except ValidationError as error:
        raise SemanticCompletionValidationError("completion envelope is invalid") from error
    try:
        decoded = json.loads(envelope.result_json)
    except (TypeError, json.JSONDecodeError) as error:
        raise SemanticCompletionValidationError("result_json is not valid JSON") from error
    if not isinstance(decoded, dict):
        raise SemanticCompletionValidationError("result_json root must be a JSON object")
    return decoded


def _validated(result: object, model: type[_StrictStageResult]) -> _StrictStageResult:
    try:
        return model.model_validate(_decoded_object(result))
    except ValidationError as error:
        raise SemanticCompletionValidationError("semantic result violates its authoritative schema") from error


def _allow_only(references: list[str], allowed_evidence_ids: set[str]) -> None:
    unsupported = set(references).difference(allowed_evidence_ids)
    if unsupported:
        raise SemanticCompletionValidationError("semantic result references evidence outside the approved bundle")


def parse_triage_completion(result: object, allowed_evidence_ids: set[str]) -> TriageDecision:
    value = _validated(result, TriageCompletion)
    _allow_only(value.relevant_evidence_ids, allowed_evidence_ids)
    return TriageDecision.from_mapping(value.model_dump())


def parse_investigation_completion(result: object, allowed_evidence_ids: set[str]) -> InvestigationAnalysis:
    value = _validated(result, InvestigationCompletion)
    # Investigation has no evidence-id field; its evidence boundary is enforced by its input bundle.
    _allow_only([], allowed_evidence_ids)
    return InvestigationAnalysis.from_mapping(value.model_dump())


def parse_challenger_completion(result: object, allowed_evidence_ids: set[str]) -> ChallengerAssessment:
    value = _validated(result, ChallengerCompletion)
    _allow_only(value.evidence_ids, allowed_evidence_ids)
    return ChallengerAssessment.from_mapping(value.model_dump())


def parse_native_triage(result: object, allowed_evidence_ids: set[str]) -> TriageDecision:
    value = _native_validated(result, TriageCompletion)
    _allow_only(value.relevant_evidence_ids, allowed_evidence_ids)
    return TriageDecision.from_mapping(value.model_dump())


def parse_native_investigation(result: object, allowed_evidence_ids: set[str]) -> InvestigationAnalysis:
    value = _native_validated(result, InvestigationCompletion)
    _allow_only([], allowed_evidence_ids)
    return InvestigationAnalysis.from_mapping(value.model_dump())


def parse_native_challenger(result: object, allowed_evidence_ids: set[str]) -> ChallengerAssessment:
    value = _native_validated(result, ChallengerCompletion)
    _allow_only(value.evidence_ids, allowed_evidence_ids)
    return ChallengerAssessment.from_mapping(value.model_dump())


def parse_native_foresight(result: object, allowed_evidence_ids: set[str], allowed_assumption_ids: set[str], allowed_result_ids: set[str]) -> dict[str, Any]:
    value = _native_validated(result, ForesightAssessmentCompletion).model_dump()
    _allow_only(value["evidence_ids"], allowed_evidence_ids)
    if set(value["assumption_ids"]).difference(allowed_assumption_ids) or set(value["scenario_result_ids"]).difference(allowed_result_ids): raise SemanticCompletionValidationError("foresight references outside approved inputs")
    return value


def parse_native_foresight_challenge(result: object, allowed_evidence_ids: set[str], allowed_assumption_ids: set[str], allowed_definition_ids: set[str], allowed_result_ids: set[str]) -> dict[str, Any]:
    value = _native_validated(result, ForesightChallengeAssessmentCompletion).model_dump()
    _allow_only(value["evidence_ids"], allowed_evidence_ids)
    if set(value["assumption_ids"]).difference(allowed_assumption_ids) or set(value["scenario_definition_ids"]).difference(allowed_definition_ids) or set(value["scenario_result_ids"]).difference(allowed_result_ids): raise SemanticCompletionValidationError("foresight challenger references outside approved inputs")
    return value

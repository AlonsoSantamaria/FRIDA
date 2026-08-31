"""Revised Target B / Option 2.5 bounded, lead-owned controlled replay.

This path references historical evidence read-only.  It does not recreate the
old CandidateSignal; the historical candidate is explicitly marked as such in
the append-only execution ledger.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from .controlled_replay import new_execution, register_execution_attempt
from .governance import evaluate
from .lead_catalogue import ALLOWED_SPECIALISTS
from .native_stage_runtime import NativeStageError, NativeStages

LEAD_CALL_LIMIT = 3
SPECIALIST_CALL_LIMIT = 3
CHALLENGER_CALL_LIMIT = 1
TOTAL_CALL_LIMIT = 8


class LeadRuntime:
    """Persisted gates make an unauthorized downstream call impossible."""

    def __init__(self, store: Any, execution_id: str, stages: NativeStages, source_observation_mode: str = "HISTORICAL_REAL", expected_attention: str | None = None, event_sink: Any = None):
        self.store, self.execution_id, self.stages = store, execution_id, stages
        self.calls = 0
        self.source_observation_mode = source_observation_mode
        self.lead_calls = 0
        self.specialist_calls = 0
        self.challenger_calls = 0
        self.expected_attention = expected_attention
        self.event_sink = event_sink

    def event(self, name: str, payload: dict[str, object]) -> None:
        public_payload = {**payload, "execution_id": self.execution_id}
        self.store.append_execution_event(self.execution_id, datetime.now(tz=UTC), name, public_payload)
        if self.event_sink:
            self.event_sink(name, public_payload)

    @staticmethod
    def _plain(value: Any) -> dict[str, object]:
        result = asdict(value) if hasattr(value, "__dataclass_fields__") else dict(value)
        if "materiality" in result and hasattr(result["materiality"], "value"):
            result["materiality"] = result["materiality"].value
        return result

    def _call(self, stage: str, fn: Any, category: str, evidence_ids: tuple[str, ...]) -> Any:
        if self.calls >= TOTAL_CALL_LIMIT:
            raise RuntimeError("lead workflow total semantic-call limit reached")
        self.event("stage.started", {"stage": stage, "configured_max_output_tokens": 4096})
        try:
            value, meta = fn()
            self.calls += 1
            if category == "lead": self.lead_calls += 1
            elif category == "specialist": self.specialist_calls += 1
            else: self.challenger_calls += 1
            self.event("stage.model_completed", {"stage": stage, **meta})
            self.event("stage.validation_passed", {"stage": stage})
            self.event("stage.evidence_allowlist_passed", {"stage": stage})
            if stage == "FRIDA Attention & Initial Plan":
                self.store.persist_execution_initial_plan(self.execution_id, self._plain(value))
            self.event("stage.semantic_artifact_persisted", {
                "stage": stage, "artifact_type": type(value).__name__,
                "artifact": self._plain(value), "approved_evidence_ids": list(evidence_ids),
            })
            return value
        except Exception as error:
            self.event("stage.runtime_failed", {"stage": stage, "error_class": type(error).__name__, "retry_count": 0})
            self.event("execution.stopped", {"stop_point": stage, "retry_count": 0})
            raise

    def _gate(self, stage: str, allowed: bool, reason: str) -> bool:
        self.event("stage.gate_opened" if allowed else "stage.gate_blocked", {"stage": stage, "gate": reason})
        return allowed

    def _specialist(self, name: str, signal: Any, evidence: tuple[Any, ...], mandate: str) -> Any:
        if name not in ALLOWED_SPECIALISTS or self.specialist_calls >= SPECIALIST_CALL_LIMIT:
            raise RuntimeError("specialist selection is unauthorized or over bound")
        fn = getattr(self.stages, name)
        return self._call(name, lambda: fn(signal, evidence, mandate), "specialist", tuple(x.evidence_id for x in evidence))

    def run(self, signal: Any, evidence: tuple[Any, ...]) -> dict[str, object]:
        ids = tuple(item.evidence_id for item in evidence)
        self.event("signal.historical_reference_confirmed" if self.source_observation_mode == "HISTORICAL_REAL" else "signal.attention_confirmed", {"signal_id": signal.signal_id, "claims_new_world_observation": False})
        attention = self._call("FRIDA Attention & Initial Plan", lambda: self.stages.lead_attention(signal, evidence), "lead", ids)
        mode = attention["attention"]
        if self.expected_attention is not None and mode != self.expected_attention:
            self.event("stage.gate_blocked", {"stage": "FRIDA Attention & Initial Plan", "gate": "CANONICAL_ATTENTION_MISMATCH"})
            self.event("execution.stopped", {"stop_point": "FRIDA Attention & Initial Plan", "retry_count": 0})
            raise RuntimeError("execution-scoped plan conflicts with canonical Attention")
        if mode != "INVESTIGATE":
            self._gate("FRIDA Attention & Initial Plan", False, mode)
            self.event("execution.completed", {"state": "SIGNAL_" + mode, "retry_count": 0, "semantic_calls": self.calls})
            return {"state": "SIGNAL_" + mode, "attention": attention, "disposition": None}
        selected, mandates = attention["selected_specialists"], attention["mandates"]
        authorized = bool(selected) and not set(selected).difference(ALLOWED_SPECIALISTS) and len(selected) == len(mandates)
        if not self._gate("FRIDA Attention & Initial Plan", authorized, "INVESTIGATE_PLAN_VALID" if authorized else "INVALID_PLAN"):
            self.event("execution.completed", {"state": "STOPPED_INVALID_PLAN", "retry_count": 0, "semantic_calls": self.calls})
            return {"state": "STOPPED_INVALID_PLAN", "attention": attention, "disposition": None}
        self.event("candidate.historical_reference_authorized" if self.source_observation_mode == "HISTORICAL_REAL" else "candidate.authorized", {"signal_id": signal.signal_id, "candidate_created": self.source_observation_mode != "HISTORICAL_REAL", "reason": "immutable historical controlled replay" if self.source_observation_mode == "HISTORICAL_REAL" else "FRIDA Attention INVESTIGATE"})
        artifacts = [self._specialist(name, signal, evidence, mandate) for name, mandate in zip(selected, mandates, strict=True)]
        review = self._call("FRIDA Evidence Review", lambda: self.stages.lead_review(attention, [self._plain(x) for x in artifacts], evidence), "lead", ids)
        if review["decision"] == "STOP":
            self._gate("FRIDA Evidence Review", False, "STOP")
            self.event("execution.completed", {"state": "LEAD_STOP", "retry_count": 0, "semantic_calls": self.calls})
            return {"state": "LEAD_STOP", "attention": attention, "review": review, "disposition": None}
        if review["decision"] == "REQUEST_ADDITIONAL_SPECIALIST":
            extra = review["additional_specialist"]
            allowed = bool(extra and review["mandate"] and extra in ALLOWED_SPECIALISTS and self.specialist_calls < SPECIALIST_CALL_LIMIT)
            if not self._gate("FRIDA Evidence Review", allowed, "ADDITIONAL_SPECIALIST" if allowed else "ADDITIONAL_SPECIALIST_BLOCKED"):
                return {"state": "LEAD_REVIEW_BLOCKED", "attention": attention, "review": review, "disposition": None}
            artifacts.append(self._specialist(str(extra), signal, evidence, str(review["mandate"])))
        else:
            self._gate("FRIDA Evidence Review", True, "READY_FOR_CHALLENGE")
        challenge = self._call("Independent Challenger", lambda: self.stages.challenger(artifacts[0], evidence), "challenger", ids)
        critical = getattr(challenge.materiality, "value", challenge.materiality) == "CRITICAL"
        if not self._gate("Independent Challenger", not critical, "CRITICAL" if critical else "CHALLENGER_ACCEPTED"):
            self.event("disposition.blocked", {"reason": "critical_challenge"})
            return {"state": "STOPPED_CRITICAL_CHALLENGE", "attention": attention, "review": review, "challenge": challenge, "disposition": None}
        interpretation = self._call("FRIDA Post-Challenge Interpretation", lambda: self.stages.lead_interpretation([self._plain(x) for x in artifacts], challenge, evidence), "lead", ids)
        governed = evaluate(list(evidence), challenge)
        self.event("disposition.completed", {"disposition": governed.disposition.value, "factors": governed.factors, "challenger_materiality": challenge.materiality.value, "lead_interpretation": interpretation["decision"]})
        self.event("execution.completed", {"state": "COMPLETED", "retry_count": 0, "semantic_calls": self.calls})
        return {"state": "COMPLETED", "attention": attention, "review": review, "artifacts": artifacts, "challenge": challenge, "interpretation": interpretation, "disposition": governed}


def execute_lead_controlled_replay(store: Any, project_root: str, candidate: Any, evidence: tuple[Any, ...], authorization_reference: str, stages: NativeStages | None = None) -> tuple[str, dict[str, object]]:
    """Register one fresh governed execution, then run forward once while green."""
    execution = new_execution(candidate, evidence, authorization_reference)
    register_execution_attempt(store, execution, project_root)
    store.append_execution_event(execution.execution_id, datetime.now(tz=UTC), "execution.started", {"architecture": "REVISED_TARGET_B_OPTION_2_5", "semantic_call_limit": TOTAL_CALL_LIMIT, "retry_count": 0})
    owned = stages is None
    stages = stages or NativeStages()
    try:
        result = LeadRuntime(store, execution.execution_id, stages).run(candidate, evidence)
        return execution.execution_id, result
    finally:
        if owned: stages.close()


def execute_lead_case(store: Any, case_id: str, candidate: Any, evidence: tuple[Any, ...], authorization_reference: str, stages: NativeStages | None = None,
                      *, execution_mode: str = "LIVE_CASE", source_observation_mode: str = "LIVE_OBSERVED", expected_attention: str | None = None, event_sink: Any = None) -> tuple[str, dict[str, object]]:
    """Use the verified Option 2.5 runtime for a new, properly linked Case."""
    from .case_spine import CaseSpine
    execution_id = CaseSpine(store).register_execution(case_id, candidate, evidence, authorization_reference, execution_mode=execution_mode, source_observation_mode=source_observation_mode)
    store.append_execution_event(execution_id, datetime.now(tz=UTC), "execution.started", {"architecture": "REVISED_TARGET_B_OPTION_2_5", "semantic_call_limit": TOTAL_CALL_LIMIT, "retry_count": 0, "execution_mode": execution_mode, "source_observation_mode": source_observation_mode})
    owned = stages is None; stages = stages or NativeStages()
    try:
        return execution_id, LeadRuntime(store, execution_id, stages, source_observation_mode, expected_attention, event_sink).run(candidate, evidence)
    finally:
        if owned: stages.close()

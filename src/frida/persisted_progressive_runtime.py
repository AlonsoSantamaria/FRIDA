"""Ledger-first progressive runtime bridge; never invoked without clearance."""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Callable

from .domain import ChallengeMateriality
from .governance import evaluate
from .orchestrator_foundation import challenger_gate, investigation_gate, triage_gate


class PersistedProgressiveRuntime:
    def __init__(self, store: Any, execution_id: str, stages: Any):
        self.store, self.execution_id, self.stages = store, execution_id, stages

    def _event(self, event_type: str, payload: dict[str, object]) -> None:
        self.store.append_execution_event(
            self.execution_id, datetime.now(tz=UTC), event_type, payload
        )

    @staticmethod
    def _artifact(stage: str, value: Any, evidence_ids: tuple[str, ...]) -> dict[str, object]:
        """Persist only the validated domain representation and traceability."""
        artifact = asdict(value)
        materiality = artifact.get("materiality")
        if materiality is not None:
            artifact["materiality"] = materiality.value
        if stage == "Investigation":
            # Its frozen schema has no evidence-ID field; record the deterministic
            # approved input bundle without changing the semantic contract.
            artifact["evidence_ids"] = list(evidence_ids)
        return {
            "stage": stage,
            "artifact_type": type(value).__name__,
            "artifact": artifact,
            "approved_evidence_ids": list(evidence_ids),
        }

    def _stage(
        self, name: str, invoke: Callable[[], tuple[Any, dict[str, object]]], evidence_ids: tuple[str, ...]
    ) -> Any:
        self._event("stage.started", {"stage": name, "configured_max_output_tokens": 4096})
        try:
            value, meta = invoke()
            self._event("stage.model_completed", {"stage": name, **meta})
            self._event("stage.validation_passed", {"stage": name})
            self._event("stage.evidence_allowlist_passed", {"stage": name})
            # A persistence failure raises and prevents the downstream gate.
            self._event("stage.semantic_artifact_persisted", self._artifact(name, value, evidence_ids))
            return value
        except Exception as error:
            self._event("stage.runtime_failed", {
                "stage": name, "error_class": type(error).__name__, "retry_count": 0,
            })
            self._event("execution.stopped", {"stop_point": name, "retry_count": 0})
            raise

    def _persist_gate(self, stage: str, gate: Any) -> bool:
        self._event("stage.gate_opened" if gate.allowed else "stage.gate_blocked", {
            "stage": stage, "gate": gate.status,
        })
        return gate.allowed

    def run(self, candidate: Any, evidence: tuple[Any, ...]) -> Any | None:
        evidence_ids = tuple(item.evidence_id for item in evidence)
        triage = self._stage("Semantic Triage", lambda: self.stages.triage(candidate, evidence), evidence_ids)
        if not self._persist_gate("Semantic Triage", triage_gate(triage)):
            return None

        investigation = self._stage("Investigation", lambda: self.stages.investigation(candidate, evidence), evidence_ids)
        if not self._persist_gate("Investigation", investigation_gate(investigation)):
            return None

        challenger = self._stage("Independent Challenger", lambda: self.stages.challenger(investigation, evidence), evidence_ids)
        if not self._persist_gate("Independent Challenger", challenger_gate(challenger)):
            return None
        if challenger.materiality is ChallengeMateriality.CRITICAL:
            self._event("disposition.blocked", {
                "reason": "critical_challenge", "challenger_materiality": challenger.materiality.value,
            })
            return None

        governed = evaluate(list(evidence), challenger)
        self._event("disposition.completed", {
            "disposition": governed.disposition.value,
            "factors": governed.factors,
            "reentry_condition": governed.reentry_condition,
            "challenger_materiality": challenger.materiality.value,
            "challenger_required_effect": challenger.required_effect,
        })
        return governed

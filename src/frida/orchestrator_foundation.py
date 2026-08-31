"""Static FRIDA Workflow foundation; it creates no runner or runtime request."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .adk_runtime import build_native_specialists

FRIDA_IDENTITY = "Autonomous Strategic Urban Intelligence Orchestrator"
FORESIGHT_CONTRACT_STATUS = "FORESIGHT_CONTRACT_REQUIRED"

@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    next_stage: str | None
    status: str

def triage_gate(value: Any) -> GateDecision:
    if value is None: return GateDecision(False, None, "TRIAGE_VALIDATION_FAILED")
    if not value.warrants_investigation: return GateDecision(False, None, "TRIAGED_OUT")
    return GateDecision(True, "investigation", "INVESTIGATION_AUTHORIZED")

def investigation_gate(value: Any) -> GateDecision:
    return GateDecision(value is not None, "independent_challenger" if value is not None else None,
                        "CHALLENGER_AUTHORIZED" if value is not None else "INVESTIGATION_VALIDATION_FAILED")

def challenger_gate(value: Any) -> GateDecision:
    return GateDecision(value is not None, "deterministic_governance" if value is not None else None,
                        "GOVERNANCE_REVIEW_AUTHORIZED" if value is not None else "CHALLENGER_VALIDATION_FAILED")

def build_frida_workflow_foundation() -> tuple[Any, dict[str, Any]]:
    from google.adk.workflow import START, Workflow
    staff = build_native_specialists()
    # These nodes are deterministic boundaries. Runtime wiring is intentionally
    # held, but their graph order is real ADK Workflow topology.
    def triage_validation_gate(): return "TRIAGE_GATE"
    def investigation_validation_gate(): return "INVESTIGATION_GATE"
    def challenger_validation_gate(): return "CHALLENGER_GATE"
    def deterministic_disposition_boundary(): return "DISPOSITION_BOUNDARY"
    workflow = Workflow(name="frida_strategic_orchestrator", edges=[(
        START, staff["semantic_triage"], triage_validation_gate,
        staff["investigation"], investigation_validation_gate,
        staff["independent_challenger"], challenger_validation_gate,
        deterministic_disposition_boundary,
    )])
    return workflow, staff

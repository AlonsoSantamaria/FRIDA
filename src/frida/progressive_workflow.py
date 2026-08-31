"""Deterministic progressive-run controller; semantic runtime remains held."""
from __future__ import annotations
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Callable
from .orchestrator_foundation import triage_gate, investigation_gate, challenger_gate

VERIFY_CAP = 4096

@dataclass
class StageAudit:
    stage: str; status: str; configured_max_output_tokens: int = VERIFY_CAP
    finish_reason: str | None = None; schema_validation: str | None = None
    evidence_allow_list: str | None = None; gate_result: str | None = None
    usage: dict[str, int] = field(default_factory=dict); latency_ms: int | None = None

@dataclass
class ProgressiveRun:
    events: list[StageAudit] = field(default_factory=list); retry_count: int = 0
    final_status: str = "NOT_STARTED"

    @property
    def total_semantic_requests(self) -> int: return sum(e.status == "COMPLETED" for e in self.events)
    @property
    def total_usage(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for event in self.events:
            for key, value in event.usage.items(): out[key] = out.get(key, 0) + value
        return out

def _validated(call: Callable[[], tuple[Any, dict[str, Any]]], stage: str, parser: Callable[[Any], Any]) -> tuple[Any | None, StageAudit]:
    started = monotonic()
    try:
        raw, meta = call(); value = parser(raw)
        audit = StageAudit(stage, "COMPLETED", finish_reason=meta.get("finish_reason"), schema_validation="PASS", evidence_allow_list="PASS", usage=meta.get("usage", {}), latency_ms=round((monotonic()-started)*1000))
        return value, audit
    except Exception:
        return None, StageAudit(stage, "STOPPED", schema_validation="FAIL", gate_result=f"{stage.upper().replace(' ', '_')}_STRUCTURED_RESULT_INVALID", latency_ms=round((monotonic()-started)*1000))

def run_progressive(triage_call, triage_parser, investigation_call, investigation_parser, challenger_call, challenger_parser) -> ProgressiveRun:
    """Exactly-once sequence; callers supply runtime only after separate clearance."""
    run = ProgressiveRun(); triage, audit = _validated(triage_call, "Semantic Triage", triage_parser); run.events.append(audit)
    gate = triage_gate(triage); audit.gate_result = gate.status
    if not gate.allowed: run.final_status = gate.status; return run
    investigation, audit = _validated(investigation_call, "Investigation", investigation_parser); run.events.append(audit)
    gate = investigation_gate(investigation); audit.gate_result = gate.status
    if not gate.allowed: run.final_status = gate.status; return run
    challenger, audit = _validated(challenger_call, "Independent Challenger", challenger_parser); run.events.append(audit)
    gate = challenger_gate(challenger); audit.gate_result = gate.status
    run.final_status = gate.status if gate.allowed else gate.status
    return run

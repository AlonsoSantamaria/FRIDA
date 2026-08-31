"""Read-only Case / Glass Hood projection for the verified Option 2.5 run."""
from __future__ import annotations

from typing import Any

from .lead_catalogue import AGENT_CATALOGUE

CANONICAL_EXECUTION_ID = "exec-controlled-replay-93a6c7ecb69741c69c18b4bea8c2c1d2"

_ACTORS = {
    "SYSTEM": {"icon": "◈", "label": "SYSTEM"},
    "FRIDA": {"icon": "✦", "label": "FRIDA"},
    "ECONOMIC": {"icon": "◫", "label": "ECONOMIC DIRECTORY CHANGE"},
    "URBAN": {"icon": "⌂", "label": "URBAN DEVELOPMENT STATUS"},
    "CHALLENGER": {"icon": "⚑", "label": "INDEPENDENT CHALLENGER"},
    "GOVERNANCE": {"icon": "◆", "label": "GOVERNANCE"},
}


def _usage(event: dict[str, Any]) -> dict[str, int]:
    usage = event["payload"].get("usage", {})
    return {
        "prompt": int(usage.get("prompt_token_count", 0)),
        "thought": int(usage.get("thoughts_token_count", 0)),
        "output": int(usage.get("candidates_token_count", 0)),
        "total": int(usage.get("total_token_count", 0)),
        "latency_ms": int(event["payload"].get("latency_ms", 0)),
    }


def build_lead_execution_projection(record: dict[str, Any]) -> dict[str, Any]:
    """Turn canonical append-only facts into a judge-readable, no-thought view."""
    events = list(record["events"])
    rows: list[dict[str, Any]] = []
    telemetry: list[dict[str, Any]] = []
    artifacts: dict[str, dict[str, Any]] = {}
    for event in events:
        kind, payload = event["event_type"], event["payload"]
        if kind == "stage.model_completed":
            telemetry.append({"stage": payload["stage"], **_usage(event)})
        elif kind == "stage.semantic_artifact_persisted":
            artifacts[payload["stage"]] = payload["artifact"]
    attention = artifacts.get("FRIDA Attention & Initial Plan", {})
    review = artifacts.get("FRIDA Evidence Review", {})
    challenge = artifacts.get("Independent Challenger", {})
    interpretation = artifacts.get("FRIDA Post-Challenge Interpretation", {})
    disposition = next((e["payload"] for e in events if e["event_type"] == "disposition.completed"), {})

    def add(actor: str, at: str, action: str, decision: str, detail: str, evidence: list[str] | None = None) -> None:
        rows.append({"at": at, "actor": _ACTORS[actor], "action": action, "decision": decision, "detail": detail, "evidence_ids": evidence or []})

    registered = next((e for e in events if e["event_type"] == "execution.registered"), None)
    signal = next((e for e in events if e["event_type"] == "signal.historical_reference_confirmed"), None)
    if registered: add("SYSTEM", registered["occurred_at"], "Observation verified", "NORMALIZED", "Historical real DENUE observation and frozen evidence were verified.")
    if signal: add("SYSTEM", signal["occurred_at"], "Signal available", "ATTENTION READY", "A historical real signal was referenced read-only; no new observation was claimed.")
    if attention:
        add("FRIDA", next(e["occurred_at"] for e in events if e["event_type"] == "stage.semantic_artifact_persisted" and e["payload"]["stage"] == "FRIDA Attention & Initial Plan"), "Attention & initial plan", str(attention.get("attention", "")), "Strategic question framed; FRIDA selected bounded specialists.", list(attention.get("relevant_evidence_ids", [])))
        for specialist, mandate in zip(attention.get("selected_specialists", []), attention.get("mandates", []), strict=False):
            actor = "ECONOMIC" if specialist == "economic_directory_change" else "URBAN"
            add("FRIDA", next(e["occurred_at"] for e in events if e["event_type"] == "stage.started" and e["payload"]["stage"] == specialist), "Specialist selected", _ACTORS[actor]["label"], str(mandate))
    for stage, actor, text in (("economic_directory_change", "ECONOMIC", "Structured evidence returned; directory changes remain administrative unless independently supported."), ("urban_development_status", "URBAN", "Structured evidence returned; geographic precision remained limited.")):
        artifact_event = next((e for e in events if e["event_type"] == "stage.semantic_artifact_persisted" and e["payload"]["stage"] == stage), None)
        if artifact_event: add(actor, artifact_event["occurred_at"], "Analysis completed", "VALIDATED", text, list(artifact_event["payload"].get("approved_evidence_ids", [])))
    if review:
        review_event = next(e for e in events if e["event_type"] == "stage.semantic_artifact_persisted" and e["payload"]["stage"] == "FRIDA Evidence Review")
        add("FRIDA", review_event["occurred_at"], "Evidence reviewed", str(review.get("decision", "")), "FRIDA decided the case was ready for independent challenge.")
    if challenge:
        challenge_event = next(e for e in events if e["event_type"] == "stage.semantic_artifact_persisted" and e["payload"]["stage"] == "Independent Challenger")
        add("CHALLENGER", challenge_event["occurred_at"], "Independent challenge", "CUESTIONAMIENTO SIGNIFICATIVO", "Spatial linkage could not be verified under unresolved geographic confidence.", list(challenge.get("evidence_ids", [])))
    if interpretation:
        interpretation_event = next(e for e in events if e["event_type"] == "stage.semantic_artifact_persisted" and e["payload"]["stage"] == "FRIDA Post-Challenge Interpretation")
        add("FRIDA", interpretation_event["occurred_at"], "Interpretation reconsidered", str(interpretation.get("decision", "")), "FRIDA restricted claims that exceeded the governed geographic evidence.")
    if disposition:
        disposition_event = next(e for e in events if e["event_type"] == "disposition.completed")
        add("GOVERNANCE", disposition_event["occurred_at"], "Governed disposition", str(disposition.get("disposition", "")), "Deterministic governance—not a model—issued the final outcome.")
    total = {key: sum(item[key] for item in telemetry) for key in ("prompt", "thought", "output", "total", "latency_ms")}
    correction = next((e for e in events if e["event_type"] == "execution.audit_correction"), None)
    case = record.get("case") or {
        "case_id": "case-historical-wp01", "title": "Verified historical WP01 case",
        "label": "CONTROLLED REPLAY · HISTORICAL REAL", "case_mode": "CONTROLLED_REPLAY",
        "source_observation_mode": record.get("source_observation_mode", "HISTORICAL_REAL"),
    }
    return {
        "execution_id": record["execution_id"], "status": "COMPLETED", "rows": rows, "telemetry": telemetry,
        "event_count": len(events),
        "signal_id": str(record.get("candidate_signal_id", "GOVERNED_SIGNAL")),
        "totals": total, "disposition": disposition.get("disposition"), "attention": attention.get("attention"),
        "attention_reason": attention.get("reason"),
        "investigation_question": attention.get("investigation_question"),
        "interpretation_artifact": interpretation,
        "challenger_artifact": challenge,
        "audit_correction": correction["payload"] if correction else None,
        "catalogue": [{"name": name, **data} for name, data in AGENT_CATALOGUE.items()] + [{"name": "foresight", "role": "separate human-authorized branch", "tools": [], "call_limit": 0}],
        "case": case,
    }


def canonical_lead_projection(store: Any) -> dict[str, Any] | None:
    record = store.execution_attempt(CANONICAL_EXECUTION_ID)
    return build_lead_execution_projection(record) if record else None


def current_lead_projection(store: Any, execution_id: str | None = None) -> dict[str, Any] | None:
    """Select a compatible persisted Option 2.5 run; never fabricate a view."""
    records = store.lead_execution_records()
    for record in records:
        if execution_id is not None and record["execution_id"] != execution_id: continue
        if any(event["event_type"] == "execution.started" and event["payload"].get("architecture") == "REVISED_TARGET_B_OPTION_2_5" for event in record["events"]):
            return build_lead_execution_projection(record)
    return None


def raw_governed_record_projection(store: Any, execution_id: str | None = None) -> dict[str, Any] | None:
    """A technical, read-only record rebuilt from canonical execution events."""
    view = current_lead_projection(store, execution_id)
    if view is None:
        return None
    audit = [
        {
            "at": row["at"],
            "stage": f"{row['actor']['label']} · {row['action']}",
            "detail": f"{row['decision']} — {row['detail']}",
        }
        for row in view["rows"]
    ]
    return {
        "run_id": view["execution_id"],
        "state": view["status"],
        "signal_id": view["signal_id"],
        "execution_mode": "CONTROLLED_REPLAY_DEMO",
        "audit": audit,
        "disposition": view["disposition"],
        "reentry_condition": "Immutable technical record reconstructed from canonical append-only execution events.",
    }

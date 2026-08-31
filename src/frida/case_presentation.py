"""Read-only, reusable Case Presentation projections."""
from __future__ import annotations
from typing import Any

from .lead_projection import build_lead_execution_projection


def lead_case(view: dict[str, Any]) -> dict[str, Any]:
    case=view["case"]
    evidence=sorted({evidence_id for row in view["rows"] for evidence_id in row.get("evidence_ids", [])})
    mode=case["source_observation_mode"]
    source = "Historical real observation" if mode == "HISTORICAL_REAL" else (
        "Approved historical evidence replayed in accelerated execution time" if mode == "ACCELERATED_HISTORICAL_REPLAY" else "Observed source signal"
    )
    disposition = view.get("disposition") or "NOT ISSUED"
    interpretation = view.get("interpretation_artifact") or {}
    uncertainties = [str(item) for item in interpretation.get("unresolved_uncertainties", [])]
    recommendation = (
        "Continue watching and request evidence that resolves the remaining governed uncertainty before supporting a stronger strategic conclusion."
        if disposition == "EVIDENCE_INSUFFICIENT" else
        "Follow the governed disposition shown below; FRIDA does not recommend action beyond the retained evidence."
    )
    return {
        "case_id": case["case_id"], "title": case["title"], "label": case["label"],
        "mode": case["case_mode"], "source_observation_mode": case["source_observation_mode"],
        "source": source,
        "attention": view.get("attention") or "GOVERNED", "question": "What can the governed evidence support?",
        "specialists": [item["role"] for item in view["catalogue"] if item["name"] != "foresight"],
        "evidence_ids": evidence, "limitations": ["Evidence limits remain binding throughout the execution."],
        "challenger": next((row["decision"] for row in view["rows"] if row["actor"]["label"] == "INDEPENDENT CHALLENGER"), "NOT REACHED"),
        "interpretation": next((row["decision"] for row in view["rows"] if row["action"] == "Interpretation reconsidered"), "NOT REACHED"),
        "disposition": disposition, "timeline": view["rows"], "telemetry": view["totals"],
        "strategic": {
            "noticed": "FRIDA detected a governed change in the retained municipal evidence and opened a bounded investigation.",
            "why": str(view.get("attention_reason") or view.get("investigation_question") or "The governed attention decision determined that the change warranted investigation."),
            "now": recommendation,
            "limitations": uncertainties,
        },
        "execution_id": view["execution_id"], "glass_hood_url": "/glass-hood?execution_id=" + view["execution_id"],
    }


def water_case(view: dict[str, Any]) -> dict[str, Any]:
    selected=view["selected"]
    return {
        "case_id": selected["case_id"], "title": "Governed Foresight case", "label": "HUMAN_REQUESTED · FORESIGHT",
        "mode": "FORESIGHT", "source_observation_mode": "HUMAN_REQUESTED",
        "source": f"{selected['measure']} · {selected['geography']}", "attention": "HUMAN_REQUESTED",
        "question": "What bounded qualitative scenarios are supported by governed evidence and explicit assumptions?",
        "specialists": ["Foresight specialist", "Independent Challenger"], "evidence_ids": selected["fact_ids"] + selected["source_ids"],
        "limitations": view["assessment"]["limitations"], "challenger": "MATERIAL",
        "interpretation": "RESTRICTED", "disposition": view["governance"].get("outcome", "RESTRICTED"),
        "timeline": [], "telemetry": {}, "execution_id": view["execution_id"], "glass_hood_url": None,
    }


def case_index(store: Any, foresight_view: dict[str, Any] | None) -> list[dict[str, Any]]:
    records=[]
    for record in store.lead_execution_records():
        if any(e["event_type"] == "execution.started" and e["payload"].get("architecture") == "REVISED_TARGET_B_OPTION_2_5" for e in record["events"]):
            records.append(lead_case(build_lead_execution_projection(record)))
    if foresight_view: records.append(water_case(foresight_view))
    return records


def select_case(store: Any, foresight_view: dict[str, Any] | None, case_id: str) -> dict[str, Any] | None:
    return next((case for case in case_index(store, foresight_view) if case["case_id"] == case_id), None)

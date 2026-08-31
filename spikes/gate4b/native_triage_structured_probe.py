"""One authorized, non-Golden native structured-output Triage probe.

This probe deliberately has no ADK task lifecycle, tools, execution ledger,
or persistence.  It verifies only Gemini/Vertex's provider-native structured
response boundary for FRIDA's frozen Semantic Triage context.
"""
from __future__ import annotations

import os
import json
import time
from dataclasses import asdict
from typing import Any

from google import genai
from google.genai import types

from frida.adk_runtime import LOCATION, MODEL, _evidence_digest
from frida.controlled_replay_run import HISTORICAL_CANDIDATE
from frida.golden_path import TriageDecision, wp01_current_evidence
from frida.persistence import StagingStore
from frida.semantic_completion import TriageCompletion

OUTPUT_CAP = 4096
_USAGE_FIELDS = (
    "cached_content_token_count",
    "candidates_token_count",
    "prompt_token_count",
    "thoughts_token_count",
    "tool_use_prompt_token_count",
    "total_token_count",
)


def _frozen_payload(database: str) -> tuple[dict[str, Any], set[str]]:
    """Load immutable historical input read-only; create no Observation or Candidate."""
    store = StagingStore(database)
    try:
        signal = store.candidate(HISTORICAL_CANDIDATE)
        if signal is None:
            raise RuntimeError("immutable historical candidate is required")
        evidence = wp01_current_evidence(__import__("datetime").datetime.now(tz=__import__("datetime").UTC))
    finally:
        store.close()
    return (
        {"signal": asdict(signal), "evidence": _evidence_digest(evidence)},
        {item.evidence_id for item in evidence},
    )


def _instruction() -> str:
    """The existing Triage responsibility, mechanically adapted to native JSON."""
    return (
        "You are FRIDA's Semantic Triage specialist. Use only the supplied evidence. "
        "Do not invent facts. Decide whether the candidate warrants bounded investigation. "
        "Return only the response-schema JSON object: no prose, markdown, tools, "
        "function calls, completion wrapper, or additional fields."
    )


def _usage(usage: Any) -> dict[str, Any]:
    data = usage.model_dump(exclude_none=True) if usage is not None else {}
    return {key: data[key] for key in _USAGE_FIELDS if key in data}


def run(database: str = "data/frida-golden-path.sqlite3") -> dict[str, Any]:
    """Make exactly one direct Vertex request and return only approved evidence."""
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") != "TRUE":
        raise RuntimeError("Vertex mode must be explicitly enabled")
    if os.environ.get("GOOGLE_CLOUD_LOCATION") != LOCATION:
        raise RuntimeError("native Triage location must remain global")
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    payload, allowed_ids = _frozen_payload(database)
    config = types.GenerateContentConfig(
        system_instruction=_instruction(),
        response_mime_type="application/json",
        response_schema=TriageCompletion,
        temperature=0,
        max_output_tokens=OUTPUT_CAP,
    )
    started = time.monotonic()
    client = genai.Client(vertexai=True, project=project, location=LOCATION)
    response = client.models.generate_content(
        model=MODEL,
        contents=str(payload),
        config=config,
    )
    candidate = response.candidates[0] if response.candidates else None
    parsed = response.parsed
    validation = "FAIL"
    allow_list = "NOT_EVALUATED"
    semantic: dict[str, Any] | None = None
    domain: dict[str, Any] | None = None
    try:
        # Revalidate even if the SDK returned a parsed Pydantic value.
        strict = TriageCompletion.model_validate(parsed)
        semantic = strict.model_dump()
        unsupported = set(strict.relevant_evidence_ids).difference(allowed_ids)
        if unsupported:
            allow_list = "FAIL"
        else:
            allow_list = "PASS"
            domain = asdict(TriageDecision.from_mapping(semantic))
            validation = "PASS"
    except Exception:
        # No raw response text/prose is retained on a failed structured path.
        validation = "FAIL"
    return {
        "diagnostic": "FRIDA_NATIVE_STRUCTURED_TRIAGE",
        "model": MODEL,
        "location": LOCATION,
        "temperature": 0,
        "output_cap": OUTPUT_CAP,
        "response_mime_type": "application/json",
        "response_schema": "TriageCompletion",
        "function_calling": "absent",
        "finish_task": "absent",
        "parsed_output_present": parsed is not None,
        "finish_reason": str(getattr(candidate, "finish_reason", None)) if candidate else None,
        "schema_validation": validation,
        "evidence_id_allow_list": allow_list,
        "semantic_result": semantic if validation == "PASS" else None,
        "domain_triage_result": domain if validation == "PASS" else None,
        "usage": _usage(getattr(response, "usage_metadata", None)),
        "response_id": getattr(response, "response_id", None),
        "model_version": getattr(response, "model_version", None),
        "latency_ms": round((time.monotonic() - started) * 1000),
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))

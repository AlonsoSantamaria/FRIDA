"""One authorized, non-Golden diagnostic of the Vertex function-call boundary.

This deliberately bypasses ADK execution.  It reads a raw Vertex response body
only in memory and emits an allow-listed structural summary; it creates no
FRIDA execution instance and never persists raw response content.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import asdict
from typing import Any

from google import genai
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from frida.adk_runtime import MODEL, TRIAGE_FIELDS, _evidence_digest, task_completion_instruction
from frida.controlled_replay_run import HISTORICAL_CANDIDATE
from frida.golden_path import wp01_current_evidence
from frida.persistence import StagingStore
from frida.semantic_completion import CompletionEnvelope

LOCATION = "global"
OUTPUT_CAP = 256
_USAGE = ("promptTokenCount", "candidatesTokenCount", "thoughtsTokenCount", "totalTokenCount")


def _safe_message(value: object) -> str | None:
    """Provider status only: strip identifiers and bound length; never retain model text."""
    if not isinstance(value, str) or not value:
        return None
    value = re.sub(r"[A-Za-z0-9_./:-]{25,}", "[REDACTED_IDENTIFIER]", value)
    return value[:240]


def _argument_shape(value: object) -> dict[str, object]:
    """Keep types and keys, not function-argument values or semantic prose."""
    if not isinstance(value, dict):
        return {"present": value is not None, "container_type": type(value).__name__}
    result: dict[str, object] = {
        "present": True,
        "container_type": "object",
        "keys": sorted(value),
        "value_types": {key: type(item).__name__ for key, item in value.items()},
    }
    result_json = value.get("result_json")
    if isinstance(result_json, str):
        try:
            decoded = json.loads(result_json)
        except json.JSONDecodeError:
            result["result_json_parse"] = "INVALID_JSON"
        else:
            result["result_json_parse"] = "OBJECT" if isinstance(decoded, dict) else type(decoded).__name__
            if isinstance(decoded, dict):
                result["result_json_object_keys"] = sorted(decoded)
    return result


def _candidate_summary(candidate: object, scalar_boundary: bool) -> dict[str, object]:
    if not isinstance(candidate, dict):
        return {"candidate_type": type(candidate).__name__}
    parts = ((candidate.get("content") or {}).get("parts") or [])
    kinds: list[str] = []
    calls: list[dict[str, object]] = []
    raw_argument_representation = False
    for part in parts:
        if not isinstance(part, dict):
            kinds.append(type(part).__name__)
            continue
        if "functionCall" in part:
            kinds.append("function_call")
            call = part.get("functionCall") or {}
            args = call.get("args") if isinstance(call, dict) else None
            raw_argument_representation = raw_argument_representation or isinstance(args, (str, bytes))
            calls.append({
                "name": call.get("name") if isinstance(call, dict) else None,
                "args_shape": _argument_shape(args),
                "result_json_is_boundary_ok": bool(
                    scalar_boundary and isinstance(args, dict) and args.get("result_json") == "BOUNDARY_OK"
                ),
            })
        elif "functionResponse" in part:
            kinds.append("function_response")
        elif "text" in part or "thought" in part:
            # Deliberately identify but never retain model text or thought.
            kinds.append("text_or_thought")
        else:
            kinds.append("other")
    return {
        "finish_reason": candidate.get("finishReason"),
        "finish_message": _safe_message(candidate.get("finishMessage")),
        "part_kinds": kinds,
        "function_calls": calls,
        "unparsed_argument_string_or_bytes_observable": raw_argument_representation,
    }


def _payload(database: str) -> tuple[dict[str, object], tuple[object, ...]]:
    store = StagingStore(database)
    try:
        signal = store.candidate(HISTORICAL_CANDIDATE)
        if signal is None:
            raise RuntimeError("immutable historical candidate is required")
        evidence = wp01_current_evidence(__import__("datetime").datetime.now(tz=__import__("datetime").UTC))
        return {"signal": asdict(signal), "evidence": _evidence_digest(evidence)}, evidence
    finally:
        store.close()


def run(database: str = "data/frida-golden-path.sqlite3", scalar_boundary: bool = False) -> dict[str, object]:
    """Issue exactly one Vertex request and return only its allow-listed evidence."""
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    if os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") != "TRUE":
        raise RuntimeError("Vertex mode must be explicitly enabled")
    if os.environ.get("GOOGLE_CLOUD_LOCATION") != LOCATION:
        raise RuntimeError("diagnostic location must remain global")
    payload, _evidence = _payload(database)
    # Building a task agent is local-only and yields the exact current declaration.
    agent = Agent(
        name="semantic_triage", model=Gemini(model=MODEL), mode="task", tools=[],
        output_schema=CompletionEnvelope,
        instruction=task_completion_instruction("Semantic Triage", TRIAGE_FIELDS),
        generate_content_config=types.GenerateContentConfig(temperature=0, max_output_tokens=OUTPUT_CAP),
    )
    declaration = agent.tools[0]._get_declaration()
    # This is the same effective task instruction: FRIDA instruction plus ADK's
    # built-in completion instruction. It contains no changed semantic prompt.
    completion_instruction = agent.tools[0]._build_instruction()
    instruction = agent.instruction
    if scalar_boundary:
        # The only authorized variable: the string value need not contain JSON.
        old = "result_json must be a JSON object string with exactly these required semantic fields: " + ", ".join(TRIAGE_FIELDS) + "."
        new = 'For this boundary diagnostic only, result_json must be exactly the scalar string "BOUNDARY_OK".'
        instruction = instruction.replace(old, new)
    config = types.GenerateContentConfig(
        system_instruction=instruction + "\n\n" + completion_instruction,
        tools=[types.Tool(function_declarations=[declaration])],
        temperature=0,
        max_output_tokens=OUTPUT_CAP,
        should_return_http_response=True,
    )
    started = time.monotonic()
    client = genai.Client(vertexai=True, project=project, location=LOCATION)
    try:
        # Private SDK method is intentional: public generate_content discards
        # the raw body after parsing, while this returns it only in memory.
        response = client.models._generate_content(model=MODEL, contents=str(payload), config=config)
        raw_body = getattr(getattr(response, "sdk_http_response", None), "body", None)
        document = json.loads(raw_body) if isinstance(raw_body, str) else {}
        candidates = document.get("candidates") if isinstance(document, dict) else None
        return {
            "diagnostic": "FRIDA_RAW_FUNCTION_CALL_BOUNDARY",
            "model": MODEL,
            "location": LOCATION,
            "temperature": 0,
            "output_cap": OUTPUT_CAP,
            "completion_value_contract": "BOUNDARY_OK" if scalar_boundary else "JSON_OBJECT_STRING",
            "completion_declaration": {"name": declaration.name, "parameters": declaration.parameters_json_schema},
            "candidate_count": len(candidates) if isinstance(candidates, list) else 0,
            "candidates": [_candidate_summary(item, scalar_boundary) for item in candidates] if isinstance(candidates, list) else [],
            "usage": {key: document.get("usageMetadata", {}).get(key) for key in _USAGE if document.get("usageMetadata", {}).get(key) is not None},
            "response_id": document.get("responseId") if isinstance(document, dict) else None,
            "model_version": document.get("modelVersion") if isinstance(document, dict) else None,
            "provider_error": None,
            "latency_ms": round((time.monotonic() - started) * 1000),
        }
    except Exception as error:
        return {
            "diagnostic": "FRIDA_RAW_FUNCTION_CALL_BOUNDARY",
            "model": MODEL, "location": LOCATION, "candidate_count": 0, "candidates": [],
            "provider_error": {
                "class": type(error).__name__,
                "status": getattr(error, "status", None),
                "code": getattr(error, "code", None),
                "details_type": type(getattr(error, "details", None)).__name__,
            },
            "latency_ms": round((time.monotonic() - started) * 1000),
        }


if __name__ == "__main__":
    scalar = "--scalar-boundary" in sys.argv[1:]
    print(json.dumps(run(scalar_boundary=scalar), ensure_ascii=False, sort_keys=True))

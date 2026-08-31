"""Gate 4B only: one bounded Vertex AI/ADK runtime capability probe.

This is deliberately not FRIDA product behavior.  It performs one direct,
structured Gemini request and one no-tools, single-turn ADK invocation, then
prints sanitized evidence.  It neither persists cloud data nor retries calls.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

from google import genai
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-east1")
MODEL = os.environ.get("FRIDA_GATE4_MODEL", "gemini-3.7-flash")


def usage_dict(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        raw = value.model_dump(exclude_none=True)
    elif isinstance(value, dict):
        raw = value
    else:
        return {"available": True}
    allowed = {"prompt_token_count", "candidates_token_count", "total_token_count"}
    return {key: raw[key] for key in allowed if key in raw}


def serializable(value: Any) -> Any:
    """Return only SDK response diagnostics; never serialize credentials."""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def response_diagnostics(response: Any) -> dict[str, Any]:
    candidates = []
    for candidate in getattr(response, "candidates", None) or []:
        candidates.append(
            {
                "finish_reason": serializable(getattr(candidate, "finish_reason", None)),
                "finish_message": getattr(candidate, "finish_message", None),
            }
        )
    prompt_feedback = serializable(getattr(response, "prompt_feedback", None))
    return {
        "candidates": candidates,
        "prompt_feedback": prompt_feedback,
        "usage": usage_dict(getattr(response, "usage_metadata", None)),
    }


def structured_result(response: Any) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    diagnostics = response_diagnostics(response)
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        return parsed, diagnostics
    if parsed is not None and hasattr(parsed, "model_dump"):
        return parsed.model_dump(exclude_none=True), diagnostics
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            diagnostics["text_result"] = "INVALID_JSON"
        else:
            if isinstance(result, dict):
                return result, diagnostics
            diagnostics["text_result"] = "JSON_NOT_OBJECT"
    elif text is None:
        diagnostics["text_result"] = "NO_TEXT"
    else:
        diagnostics["text_result"] = "EMPTY_TEXT"
    return None, diagnostics


def sanitized_error(exc: Exception) -> dict[str, str]:
    """Keep diagnostic status/message while never emitting credential material."""
    message = str(exc).replace(PROJECT, "[PROJECT]")
    for marker in ("Bearer ", "access_token", "refresh_token"):
        if marker in message:
            message = message.split(marker, 1)[0] + "[REDACTED]"
    return {"status": "BLOCKED", "error_type": type(exc).__name__, "message": message}


def direct_probe() -> dict[str, Any]:
    started = time.monotonic()
    client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
    response = client.models.generate_content(
        model=MODEL,
        contents="Return JSON only: {\"runtime\":\"ok\"}.",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {"runtime": {"type": "string", "enum": ["ok"]}},
                "required": ["runtime"],
            },
            temperature=0,
            max_output_tokens=256,
        ),
    )
    result, diagnostics = structured_result(response)
    valid = result == {"runtime": "ok"}
    return {
        "status": "PASS" if valid else "INVALID_STRUCTURED_RESPONSE",
        "model": MODEL,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "response_json": result,
        **diagnostics,
    }


async def adk_probe() -> dict[str, Any]:
    started = time.monotonic()
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="gate4b_probe", user_id="gate4b", session_id="single_run"
    )
    agent = Agent(
        name="gate4b_runtime_agent",
        model=Gemini(model=MODEL),
        instruction=(
            "When the runtime-confirmation task is complete, call the "
            "automatically supplied finish_task tool with "
            '{"result":"ADK_RUNTIME_OK"}. Do not emit accompanying text.'
        ),
        tools=[],
        mode="task",
        generate_content_config=types.GenerateContentConfig(
            temperature=0, max_output_tokens=128
        ),
    )
    runner = Runner(agent=agent, app_name="gate4b_probe", session_service=session_service)
    terminal_output = None
    model_content = []
    usage = None
    finish_task_called = False
    async for event in runner.run_async(
        user_id="gate4b",
        session_id=session.id,
        new_message=types.Content(
            role="user", parts=[types.Part(text="Confirm runtime availability.")]
        ),
    ):
        finish_task_called = finish_task_called or any(
            call.name == "finish_task" for call in event.get_function_calls()
        )
        if event.content and event.content.parts:
            model_content.extend(
                part.text for part in event.content.parts if getattr(part, "text", None)
            )
        if event.output is not None:
            # Root task-mode agents place their terminal result here.
            terminal_output = event.output
        if getattr(event, "usage_metadata", None) is not None:
            usage = event.usage_metadata
    result_value = (
        terminal_output.get("result") if isinstance(terminal_output, dict) else None
    )
    return {
        "status": "PASS" if result_value == "ADK_RUNTIME_OK" else "UNEXPECTED_RESPONSE",
        "model": MODEL,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "finish_task_called": finish_task_called,
        "result_value": result_value,
        "terminal_output": serializable(terminal_output),
        "model_content": model_content,
        "usage": usage_dict(usage),
    }


def main() -> None:
    evidence: dict[str, Any] = {
        "probe": "gate4b_real_runtime_capability",
        "project": PROJECT,
        "location": LOCATION,
        "direct_structured_gemini": None,
        "adk_orchestrated": None,
    }
    adk_only = os.environ.get("FRIDA_GATE4_PROBE_MODE") == "adk_only"
    if adk_only:
        evidence["direct_structured_gemini"] = {
            "status": "PREVIOUSLY_PASSED",
            "reason": "Gate 4B ADK-mode correction; no additional direct request",
        }
    else:
        try:
            evidence["direct_structured_gemini"] = direct_probe()
        except Exception as exc:  # A failure is recorded; do not retry.
            evidence["direct_structured_gemini"] = sanitized_error(exc)
    if evidence["direct_structured_gemini"]["status"] in {"PASS", "PREVIOUSLY_PASSED"}:
        try:
            evidence["adk_orchestrated"] = asyncio.run(adk_probe())
        except Exception as exc:  # A failure is recorded; do not retry.
            evidence["adk_orchestrated"] = sanitized_error(exc)
    else:
        evidence["adk_orchestrated"] = {"status": "NOT_RUN", "reason": "direct probe blocked"}
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

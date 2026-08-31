"""Native structured specialist definitions; no runtime execution."""
from __future__ import annotations
from typing import Any
from .domain import Evidence

MODEL = "gemini-3.6-flash"
LOCATION = "global"

def task_completion_instruction(role: str, fields: dict[str, str]) -> str:
    """Historical helper retained only for immutable execution evidence tests."""
    return f"Historical finish_task instruction for {role}: the only permitted completion is call finish_task exactly once with fields " + ", ".join(fields) + ". Do not ask questions."

def sanitized_usage_metadata(usage: Any) -> dict[str, Any]:
    data = usage.model_dump(exclude_none=True) if usage is not None else {}
    return {k: data[k] for k in ("prompt_token_count", "candidates_token_count", "thoughts_token_count", "total_token_count") if k in data}

def sanitized_event_shape(event: Any) -> dict[str, Any]:
    parts = getattr(getattr(event, "content", None), "parts", None) or []
    kinds = ["function_call" if getattr(p, "function_call", None) else "function_response" if getattr(p, "function_response", None) else "text" if getattr(p, "text", None) is not None else "other" for p in parts]
    calls = [x.name for x in event.get_function_calls()] if hasattr(event, "get_function_calls") else []
    responses = [x.name for x in event.get_function_responses()] if hasattr(event, "get_function_responses") else []
    return {"event_type": type(event).__name__, "content_part_kinds": kinds,
            "function_calls": calls, "function_responses": responses, "finish_reason": None,
            "turn_complete": bool(getattr(event, "turn_complete", False)),
            "turn_complete_reason": None, "is_final_response": False,
            "terminal_output_present": getattr(event, "output", None) is not None}

def _evidence_digest(evidence: tuple[Evidence, ...]) -> list[dict[str, Any]]:
    return [{"id": x.evidence_id, "source": x.source_id, "reference": x.source_reference,
             "hash": x.content_hash, "class": x.evidence_class.value,
             "geographic_confidence": x.geographic_confidence.value, "payload": x.payload}
            for x in evidence]

def build_native_specialists() -> dict[str, Any]:
    """Build ADK single_turn staff only; no Runner or request is created."""
    from google.adk.agents import Agent
    from google.adk.models import Gemini
    from google.genai import types
    from .semantic_completion import TriageCompletion, InvestigationCompletion, ChallengerCompletion
    common = dict(model=Gemini(model=MODEL), mode="single_turn", tools=[],
                  generate_content_config=types.GenerateContentConfig(temperature=0))
    def instruction(role: str) -> str:
        return (f"You are FRIDA's {role} specialist. Use only approved evidence. "
                "Do not invent facts. Return only the response-schema JSON object.")
    return {
        "semantic_triage": Agent(name="semantic_triage", output_schema=TriageCompletion,
                                  instruction=instruction("Semantic Triage"), **common),
        "investigation": Agent(name="investigation", output_schema=InvestigationCompletion,
                               instruction=instruction("Investigation"), **common),
        "independent_challenger": Agent(name="independent_challenger", output_schema=ChallengerCompletion,
                                        instruction=instruction("Independent Challenger"), **common),
    }

class NativeWorkflowRuntimeHold(RuntimeError): pass

class AdkTaskTerminalError(NativeWorkflowRuntimeHold):
    def __init__(self, role: str, diagnostic: dict[str, Any] | None = None):
        super().__init__("Native semantic runtime requires FRIDA Workflow authorization")
        self.role, self.diagnostic = role, diagnostic or {}

class AdkGoldenPathStages:
    """Retired direct task adapter: FRIDA Workflow owns future runtime."""
    def __init__(self, *args: Any, **kwargs: Any): self.metrics = {}; self.current_role = None
    def _held(self, role: str) -> None:
        self.current_role = role
        raise AdkTaskTerminalError(role)
    def triage(self, *args: Any, **kwargs: Any): self._held("Semantic Triage")
    def investigate(self, *args: Any, **kwargs: Any): self._held("Investigation")
    def challenge(self, *args: Any, **kwargs: Any): self._held("Independent Challenger")

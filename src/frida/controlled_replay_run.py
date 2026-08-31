"""Explicit, future-only controlled replay entrypoint.

It never creates a source observation or candidate.  `--execute` remains an
Architecture/Product runtime checkpoint and is intentionally not used by local
tests.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from .native_stage_runtime import NativeStages
from .persisted_progressive_runtime import PersistedProgressiveRuntime
from .controlled_replay import (
    EXECUTION_MODE, ORIGINAL_EXECUTION_REFERENCE, SOURCE_OBSERVATION_MODE,
    new_execution, register_execution_attempt,
)
from .golden_path import wp01_current_evidence
from .persistence import StagingStore

HISTORICAL_CANDIDATE = "signal-cb43c4e133eb3f1f"


def runtime_failure_payload(error: Exception, failed_stage: str) -> dict[str, object]:
    """Persist only classification, never credentials, response/model text, or tracebacks."""
    name = type(error).__name__
    transport_names = {"TransportError", "ConnectionError", "TimeoutError", "SSLError"}
    return {
        "terminal_outcome": "GOLDEN_PATH_BLOCKED",
        "failed_stage": failed_stage,
        "failure_phase": "RUNTIME_TRANSPORT" if name in transport_names else "RUNTIME_EXECUTION",
        "error_class": name,
        "category": "TRANSPORT" if name in transport_names else "RUNTIME",
        "retry_count": 0,
        "usage": {},
    }


def stopped_runtime_failure_view(execution_id: str, candidate_id: str, now: datetime,
                                 payload: dict[str, object]) -> dict[str, object]:
    """A projection for a new failed execution; historical projections stay untouched."""
    return {
        "run_id": execution_id, "signal_id": candidate_id, "state": "STOPPED_RUNTIME_FAILURE",
        "execution_mode": EXECUTION_MODE, "source_observation_mode": SOURCE_OBSERVATION_MODE,
        "original_execution_reference": ORIGINAL_EXECUTION_REFERENCE, "disposition": None,
        "audit": [{"at": now.isoformat(), "stage": "execution.stopped_runtime_failure",
                   "detail": str(payload["failed_stage"]), "metadata": payload}],
    }


def governed_execution_view(store: StagingStore, execution_id: str, candidate_id: str,
                            disposition: object, factors: dict[str, bool],
                            retry_count: int = 0) -> dict[str, object]:
    """Read an append-only ledger into a safe, judge-visible projection."""
    record = store.execution_attempt(execution_id)
    if record is None:
        raise ValueError("governed projection requires its append-only execution")
    artifacts: dict[str, object] = {}
    audit: list[dict[str, object]] = []
    for event in record["events"]:
        payload = event["payload"]
        audit.append({"at": event["occurred_at"], "stage": event["event_type"], "metadata": payload})
        if event["event_type"] == "stage.semantic_artifact_persisted":
            artifacts[str(payload["artifact_type"])] = payload["artifact"]
    return {
        "run_id": execution_id,
        "signal_id": candidate_id,
        "state": "COMPLETED",
        "execution_mode": EXECUTION_MODE,
        "source_observation_mode": SOURCE_OBSERVATION_MODE,
        "original_execution_reference": ORIGINAL_EXECUTION_REFERENCE,
        "triage": artifacts.get("TriageDecision"),
        "investigation": artifacts.get("InvestigationAnalysis"),
        "challenger": artifacts.get("ChallengerAssessment"),
        "disposition": disposition,
        "disposition_factors": factors,
        "retry_count": retry_count,
        "audit": audit,
    }


def execute(database_path: str, project_root: str, authorization_reference: str,
            now: datetime | None = None) -> dict[str, object]:
    """One new append-only execution over the read-only historical candidate."""
    now = now or datetime.now(tz=UTC)
    store = StagingStore(database_path)
    try:
        candidate = store.candidate(HISTORICAL_CANDIDATE)
        if candidate is None:
            raise RuntimeError("historical candidate is required and must not be recreated")
        evidence = wp01_current_evidence(now)
        execution = new_execution(candidate, evidence, authorization_reference, now)
        register_execution_attempt(store, execution, project_root)
        store.append_execution_event(execution.execution_id, now, "execution.started", {"semantic_stage_budget": 3})
        stages = NativeStages()
        progressive = PersistedProgressiveRuntime(store, execution.execution_id, stages)
        try:
            challenger = progressive.run(candidate, evidence)
        except Exception as error:
            failed_stage = getattr(error, "stage", None) or "Semantic Triage"
            payload = runtime_failure_payload(error, failed_stage)
            store.append_execution_event(execution.execution_id, now, "execution.stopped_runtime_failure", payload)
            store.save_golden_path_view(stopped_runtime_failure_view(execution.execution_id, candidate.signal_id, now, payload))
            raise
        finally:
            # The client is execution-scoped, never request-scoped.  This also
            # guarantees cleanup after a governed stage failure.
            close = getattr(stages, "close", None)
            if callable(close):
                close()
        if challenger is None:
            view = {"run_id": execution.execution_id, "state": "GOVERNANCE_STOPPED", "audit": []}
        else:
            view = {"run_id": execution.execution_id, "state": "COMPLETED", "audit": [],
                    "disposition": challenger.disposition.value, "disposition_factors": challenger.factors,
                    "retry_count": 0}
        store.append_execution_event(execution.execution_id, now, "execution.completed", {"state": view["state"], "retry_count": 0})
        if challenger is not None:
            view = governed_execution_view(
                store, execution.execution_id, candidate.signal_id,
                challenger.disposition.value, challenger.factors,
            )
            store.save_golden_path_view(view)
        return view
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="FRIDA governed controlled replay")
    parser.add_argument("--execute", action="store_true", help="required: invokes exactly the authorized semantic stages")
    parser.add_argument("--database", default="data/frida-golden-path.sqlite3")
    parser.add_argument("--authorization-reference", required=True)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("CONTROLLED REPLAY PRE-RUNTIME READY: --execute requires a new Architecture/Product runtime authorization")
    print(execute(str(Path(args.database)), args.project_root, args.authorization_reference))


if __name__ == "__main__":
    main()

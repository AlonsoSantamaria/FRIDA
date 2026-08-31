"""Explicit, one-time controlled entrypoint for the real Golden Path run.

It never runs unless the caller supplies `--execute`, which is intentionally
reserved for the Architecture/Product runtime checkpoint.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from .adk_runtime import AdkGoldenPathStages, AdkTaskTerminalError
from .domain import EvidenceClass
from .golden_path import GoldenPathOrchestrator, wp01_current_evidence
from .observation import DenueObserver, ReplaySnapshot, validate_and_prepare
from .persistence import StagingStore

DENUE_0526_HASH = "2ea1e298086f109cdbdb6a036d6cd3ecfbdfe26123b34248d73b1d06c201304a"
DENUE_0526_REFERENCE = "data/source-validation/wp01/denue/raw/denue_22_0526_corrected_csv.zip"


def approved_observation(now: datetime) -> ReplaySnapshot:
    return ReplaySnapshot(
        source_id="DENUE", source_reference=DENUE_0526_REFERENCE,
        source_date=datetime(2026, 7, 1, tzinfo=UTC), content_hash=DENUE_0526_HASH,
        evidence_class=EvidenceClass.REAL, replay_sequence=2, observed_at=now,
    )


def runtime_failure_view(signal_id: str, now: datetime, diagnostic: dict[str, object]) -> dict[str, object]:
    """A future failure is durable without exposing model text or hidden reasoning."""
    return {
        "run_id": "run-" + signal_id,
        "signal_id": signal_id,
        "state": "STOPPED_RUNTIME_FAILURE",
        "disposition": None,
        "audit": [{"at": now.isoformat(), "stage": "semantic_triage.failed", "detail": "terminal_output_missing", "metadata": diagnostic}],
    }


def execute(database_path: str, now: datetime | None = None) -> dict[str, object]:
    """Execute once; duplicate observation stops before any semantic invocation."""
    now = now or datetime.now(tz=UTC)
    snapshot = approved_observation(now)
    store = StagingStore(database_path)
    try:
        if not store.reserve_observation(snapshot):
            raise RuntimeError("approved observation already processed; refusing runtime retry")
        result = validate_and_prepare(DenueObserver(), snapshot)
        store.record_audit(result.audit)
        if result.candidate_signal is None or not result.triage_pending:
            raise RuntimeError("approved observation did not reach semantic triage boundary")
        store.record_candidate(result.candidate_signal)
        try:
            run = GoldenPathOrchestrator(AdkGoldenPathStages()).run(
                result.candidate_signal, wp01_current_evidence(now), now
            )
        except AdkTaskTerminalError as error:
            store.save_golden_path_view(runtime_failure_view(result.candidate_signal.signal_id, now, error.diagnostic))
            raise
        store.save_golden_path_view(run.view_model())
        return run.view_model()
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="FRIDA controlled Golden Path execution")
    parser.add_argument("--execute", action="store_true", help="required: performs real ADK calls")
    parser.add_argument("--database", default="data/frida-golden-path.sqlite3")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("PRE-RUNTIME READY: use --execute only after Architecture/Product authorization")
    print(execute(str(Path(args.database))))


if __name__ == "__main__":
    main()

"""One explicitly authorized Revised Target B / Option 2.5 controlled run."""
from __future__ import annotations

import argparse
from pathlib import Path

from .controlled_replay_run import HISTORICAL_CANDIDATE
from .golden_path import wp01_current_evidence
from .lead_runtime import execute_lead_controlled_replay
from .persistence import StagingStore
from .runtime_bootstrap import preflight


def execute(database: str, project_root: str, authorization_reference: str) -> dict[str, object]:
    ready = preflight()
    if ready.state != "READY":
        return {"state": "AUTH_CONTEXT_UNAVAILABLE", "checks": ready.checks, "project": ready.project}
    store = StagingStore(database)
    try:
        candidate = store.candidate(HISTORICAL_CANDIDATE)
        if candidate is None:
            raise RuntimeError("immutable historical candidate is unavailable")
        execution_id, result = execute_lead_controlled_replay(
            store, project_root, candidate, wp01_current_evidence(__import__("datetime").datetime.now(__import__("datetime").UTC)), authorization_reference
        )
        return {"execution_id": execution_id, "result": _safe(result), "preflight": ready.checks}
    finally:
        store.close()


def _safe(value: object) -> object:
    """CLI output deliberately excludes model prose beyond governed artifacts."""
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, list): return [_safe(item) for item in value]
    if hasattr(value, "value"): return value.value
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict
        return _safe(asdict(value))
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="FRIDA Option 2.5 controlled replay")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--database", default="data/frida-golden-path.sqlite3")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--authorization-reference", required=True)
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("--execute requires explicit Architecture/Product authorization")
    print(execute(str(Path(args.database)), args.project_root, args.authorization_reference))


if __name__ == "__main__":
    main()

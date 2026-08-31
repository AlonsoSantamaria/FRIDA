"""One controlled Planning SW8 + TfL Victoria research appraisal in a temporary ledger."""
from __future__ import annotations

import json
from pathlib import Path

from frida.bounded_research import BoundedLondonResearch
from frida.persistence import StagingStore


def main() -> None:
    store = StagingStore(Path("data") / "frida-bounded-research-repeat.sqlite3")
    try:
        assignment = store.activate_london_assignment()
        research = BoundedLondonResearch(store)
        try:
            result, meta, evidence = research.run_once(assignment["assignment_id"])
        finally:
            research.close()
        print(json.dumps({"result": result, "runtime_meta": meta, "evidence": evidence, "candidate_count": store.status()["candidate_signals"], "case_count": store.status().get("cases", 0), "persistence": "data/frida-bounded-research-repeat.sqlite3"}, sort_keys=True))
    finally:
        store.close()


if __name__ == "__main__":
    main()

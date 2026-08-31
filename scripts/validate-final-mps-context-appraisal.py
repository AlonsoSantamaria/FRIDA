"""One final bounded First Appraisal of MPS context beside governed London facts."""
from __future__ import annotations

import json
from pathlib import Path

from frida.first_appraisal import FirstAppraisalService
from frida.london_safety import fetch_mps_borough_safety
from frida.persistence import StagingStore


def main() -> None:
    path = Path("data") / "frida-final-london-appraisal.sqlite3"
    store = StagingStore(path)
    service = FirstAppraisalService(store)
    try:
        assignment = store.activate_london_assignment()["assignment_id"]
        snapshot = fetch_mps_borough_safety()
        store.append_source_fabric_observation(snapshot.persisted(), "ORDINARY_CHANGE", assignment)
        rows = []
        for source_id in (
            "LONDON_PLANNING_SW8", "LONDON_TFL_VICTORIA", "LONDON_EA_THAMES_TIDEWAY",
            "LONDON_GLA_HOUSING_LED_SW8", "LONDON_MPS_BOROUGH_SAFETY_SW8",
        ):
            row = store.latest_source_fabric_observation(source_id, assignment)
            if row is None:
                raise RuntimeError(f"missing governed London context: {source_id}")
            rows.append(row)
        result, meta = service.appraise(assignment, rows)
        print(json.dumps({"result": result, "runtime_meta": meta,
                          "evidence_source_ids": [row["source_id"] for row in rows],
                          "semantic_calls": 1, "retries": 0, "persistence": str(path)}, sort_keys=True))
    finally:
        service.close()
        store.close()


if __name__ == "__main__":
    main()

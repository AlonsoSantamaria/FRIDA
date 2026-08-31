"""One controlled, non-authorizing Gemini validation over frozen London Time Travel facts."""
from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from frida.first_appraisal import FirstAppraisalService
from frida.london_time_travel import SEQUENCE
from frida.persistence import StagingStore


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="frida-first-appraisal-") as directory:
        store = StagingStore(Path(directory) / "validation.sqlite3")
        try:
            assignment = store.activate_london_assignment()
            rows = []
            for step in SEQUENCE[:3]:
                snapshot = {
                    "source_id": "LONDON_PLANNING_SW8",
                    "authority": "Greater London Authority Planning London Datahub",
                    "source_url": "https://planningdata.london.gov.uk/",
                    "retrieved_at": datetime.now(tz=UTC).isoformat(),
                    "source_timestamp": step.source_date.isoformat(),
                    "geography": {"coverage": "Battersea / SW8", "kind": "development lifecycle"},
                    "fingerprint_sha256": step.content_hash,
                    "adapter_version": "london-time-travel-v1",
                    "normalization_version": "london-time-travel-v1",
                    "canonical_state": step.facts,
                }
                store.append_source_fabric_observation(snapshot, "ORDINARY_CHANGE", assignment["assignment_id"])
                rows.append(store.latest_source_fabric_observation("LONDON_PLANNING_SW8", assignment["assignment_id"]))
            service = FirstAppraisalService(store)
            try:
                result, meta = service.appraise(assignment["assignment_id"], rows)
            finally:
                service.close()
            print(json.dumps({"result": result, "runtime_meta": meta, "candidate_count": store.status()["candidate_signals"], "case_count": store.status().get("cases", 0)}, sort_keys=True))
        finally:
            store.close()


if __name__ == "__main__":
    main()

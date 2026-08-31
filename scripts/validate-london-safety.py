"""Model-free operational validation for the aggregate London safety adapter."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from frida.london_safety import fetch_mps_borough_safety
from frida.persistence import StagingStore
from frida.source_registry import SourceProposal, SourceRegistry


def main() -> None:
    snapshot = fetch_mps_borough_safety()
    with tempfile.TemporaryDirectory(prefix="frida-london-safety-") as directory:
        store = StagingStore(Path(directory) / "validation.sqlite3")
        try:
            assignment = store.activate_london_assignment()["assignment_id"]
            observation_id = store.append_source_fabric_observation(snapshot.persisted(), "ORDINARY_CHANGE", assignment)
            proposal = SourceProposal(
                "MPS Recorded Crime: Geographic Breakdown", "Metropolitan Police Service via London Datastore",
                snapshot.source_url, "Lambeth and Wandsworth borough context for SW8", "OPEN_DATA",
                ("urban-safety", "public-realm", "accessibility"),
                "Aggregate place-based safety context may reduce a declared urban-context uncertainty.",
                "Aggregate safety dynamics", "Official MPS aggregate borough publication; no person-level use.",
                "Monthly", "Three-month aggregate borough crime-category context; retrieval time excluded from state fingerprint",
                "AGGREGATE_ONLY", "OFFICIAL",
            )
            registry = SourceRegistry(store).remember(assignment, proposal, operationally_validated=True)
            print(json.dumps({"source_id": snapshot.source_id, "fingerprint_sha256": snapshot.fingerprint_sha256,
                              "source_timestamp": snapshot.source_timestamp, "observation_id": observation_id,
                              "registry": registry, "groups": len(snapshot.canonical_state["groups"]),
                              "model_calls": 0, "personal_data_processed": False}, sort_keys=True))
        finally:
            store.close()


if __name__ == "__main__":
    main()

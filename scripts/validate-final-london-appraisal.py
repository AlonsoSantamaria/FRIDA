"""One bounded four-source London synthesis, persisted as a sanitized research artifact."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from frida.london_observation import (
    EA_THAMES_TIDEWAY, GLA_HOUSING_LED, PLANNING_SW8, TFL_VICTORIA,
    LondonObservationFabricProvider,
)
from frida.native_stage_runtime import NativeStages
from frida.persistence import StagingStore

SOURCES = (PLANNING_SW8, TFL_VICTORIA, EA_THAMES_TIDEWAY, GLA_HOUSING_LED)
HYPOTHESIS = "Whether SW8/Battersea development progression and projected housing-led population growth create a strategic urban capacity or resilience question."


def main() -> None:
    path = Path("data") / "frida-final-london-appraisal.sqlite3"
    store = StagingStore(path)
    stages = NativeStages()
    try:
        assignment = store.activate_london_assignment()["assignment_id"]
        source_errors: dict[str, str | None] = {}
        provider = LondonObservationFabricProvider(
            due_source_ids=lambda: SOURCES,
            source_completed=lambda source_id, error: source_errors.__setitem__(source_id, error),
        )
        snapshots = provider.snapshots()
        actual = {item.source_id for item in snapshots}
        if actual != set(SOURCES):
            raise RuntimeError(f"four-source bundle incomplete: {sorted(actual)}; errors={source_errors}")
        evidence = []
        for snapshot in snapshots:
            persisted = snapshot.persisted()
            store.append_source_fabric_observation(persisted, "ORDINARY_CHANGE", assignment)
            row = store.latest_source_fabric_observation(str(persisted["source_id"]), assignment)
            evidence.append({
                "evidence_id": str(row["source_observation_id"]), "source_id": str(row["source_id"]),
                "source_timestamp": row["source_timestamp"],
                "geography": json.loads(str(row["provenance_json"])).get("geography"),
                "normalized_state": json.loads(str(row["canonical_state_json"])),
            })
        canonical = json.dumps({"assignment_id": assignment, "hypothesis": HYPOTHESIS, "evidence": evidence}, sort_keys=True, separators=(",", ":"))
        bundle = {"assignment_id": assignment, "starting_hypothesis": HYPOTHESIS, "evidence": evidence,
                  "research_scope": list(SOURCES), "retrieved_at": datetime.now(tz=UTC).isoformat(),
                  "input_fingerprint_sha256": sha256(canonical.encode()).hexdigest()}
        result, meta = stages.enriched_appraisal(bundle, {item["evidence_id"] for item in evidence})
        store.append_bounded_research_appraisal("bounded-research-" + uuid4().hex, assignment, bundle, "VALIDATED", result, meta)
        print(json.dumps({"result": result, "runtime_meta": meta, "evidence": evidence,
                          "semantic_calls": 1, "retries": 0, "persistence": str(path)}, sort_keys=True))
    finally:
        stages.close()
        store.close()


if __name__ == "__main__":
    main()

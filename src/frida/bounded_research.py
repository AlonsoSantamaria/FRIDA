"""One bounded two-source research pass; no Signal/Candidate/Case authority."""
from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Any
from uuid import uuid4

from .london_observation import LondonObservationFabricProvider, PLANNING_SW8, TFL_VICTORIA
from .native_stage_runtime import NativeStages

STARTING_HYPOTHESIS = "Whether major SW8/Battersea development progression may affect long-term urban infrastructure capacity."
ALLOWED_SOURCES = (PLANNING_SW8, TFL_VICTORIA)


class BoundedLondonResearch:
    def __init__(self, store: Any, provider: LondonObservationFabricProvider | None = None, stages: NativeStages | None = None):
        self.store, self.provider, self.stages = store, provider, stages or NativeStages()

    def run_once(self, assignment_id: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        if assignment_id != "LONDON_FINAL_ACTIVE":
            raise ValueError("bounded research is London-assignment only")
        provider = self.provider or LondonObservationFabricProvider(due_source_ids=lambda: ALLOWED_SOURCES)
        snapshots = provider.snapshots()
        if {item.source_id for item in snapshots} != set(ALLOWED_SOURCES):
            raise RuntimeError("authorized two-source research bundle is incomplete")
        rows = []
        for snapshot in snapshots:
            persisted = snapshot.persisted()
            observation_id = self.store.append_source_fabric_observation(persisted, "ORDINARY_CHANGE", assignment_id)
            rows.append(self.store.latest_source_fabric_observation(str(persisted["source_id"]), assignment_id))
        evidence = []
        for row in rows:
            import json
            provenance = json.loads(str(row["provenance_json"]))
            evidence.append({"evidence_id": row["source_observation_id"], "source_id": row["source_id"], "source_timestamp": row["source_timestamp"], "geography": provenance.get("geography"), "normalized_state": json.loads(str(row["canonical_state_json"]))})
        canonical = json.dumps({"assignment_id": assignment_id, "starting_hypothesis": STARTING_HYPOTHESIS, "evidence": evidence, "research_scope": list(ALLOWED_SOURCES)}, sort_keys=True, separators=(",", ":"))
        bundle = {"assignment_id": assignment_id, "starting_hypothesis": STARTING_HYPOTHESIS, "evidence": evidence, "research_scope": list(ALLOWED_SOURCES), "retrieved_at": datetime.now(tz=UTC).isoformat(), "input_fingerprint_sha256": sha256(canonical.encode()).hexdigest()}
        research_id = "bounded-research-" + uuid4().hex
        try:
            result, meta = self.stages.enriched_appraisal(bundle, {str(item["evidence_id"]) for item in evidence})
        except Exception as error:
            self.store.append_bounded_research_appraisal(research_id, assignment_id, bundle, "RUNTIME_FAILED", None, getattr(error, "meta", {"error_class": type(error).__name__}))
            raise
        self.store.append_bounded_research_appraisal(research_id, assignment_id, bundle, "VALIDATED", result, meta)
        return result, meta, evidence

    def close(self) -> None:
        self.stages.close()

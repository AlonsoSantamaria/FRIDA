"""Bounded, non-authorizing cognitive appraisal for a validated source-state change."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable
from uuid import uuid4

from .native_stage_runtime import NativeStageError, NativeStages

HOURLY_CAP = 6
DAILY_CAP = 24
APPRAISAL_VERSION = "first-appraisal-v1"


class FirstAppraisalBlocked(RuntimeError):
    pass


def compact_bundle(assignment_id: str, observations: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Expose only normalized facts/provenance needed for one bounded appraisal."""
    evidence = []
    for observation in observations:
        provenance = json.loads(str(observation["provenance_json"]))
        state = json.loads(str(observation["canonical_state_json"]))
        evidence.append({
            "evidence_id": str(observation["source_observation_id"]),
            "source_id": str(observation["source_id"]),
            "classification": str(observation["classification"]),
            "source_timestamp": observation.get("source_timestamp"),
            "geography": provenance.get("geography"),
            "normalized_state": state,
        })
    if not evidence:
        raise FirstAppraisalBlocked("no approved changed source state")
    canonical = json.dumps({"assignment_id": assignment_id, "evidence": evidence}, sort_keys=True, separators=(",", ":"))
    return {
        "contract_version": APPRAISAL_VERSION,
        "assignment_id": assignment_id,
        "evidence": evidence,
        "input_fingerprint_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
    }


class FirstAppraisalService:
    """Runs at most one model appraisal per canonical change bundle; never dispatches research."""

    def __init__(self, store: Any, stages: NativeStages | None = None):
        self.store = store
        self.stages = stages or NativeStages()

    def _assert_budget(self, assignment_id: str, now: datetime) -> None:
        if self.store.first_appraisal_count_since(assignment_id, now - timedelta(hours=1)) >= HOURLY_CAP:
            raise FirstAppraisalBlocked("hourly first-appraisal cap reached")
        if self.store.first_appraisal_count_since(assignment_id, now - timedelta(days=1)) >= DAILY_CAP:
            raise FirstAppraisalBlocked("daily first-appraisal cap reached")

    def appraise(self, assignment_id: str, observations: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
        now = datetime.now(tz=UTC)
        bundle = compact_bundle(assignment_id, observations)
        existing = self.store.first_appraisal_by_fingerprint(assignment_id, bundle["input_fingerprint_sha256"])
        if existing:
            raise FirstAppraisalBlocked("canonical change bundle already appraised")
        self._assert_budget(assignment_id, now)
        evidence_ids = {str(item["evidence_id"]) for item in bundle["evidence"]}
        record_id = "first-appraisal-" + uuid4().hex
        try:
            result, meta = self.stages.first_appraisal(bundle, evidence_ids)
        except NativeStageError as error:
            self.store.append_first_appraisal(record_id, assignment_id, bundle, "RUNTIME_FAILED", None, error.meta)
            raise
        # Research is a declared need only. This implementation does not acquire
        # any further source state; it leaves that later boundary explicit.
        merged = {
            **result,
            "research_dispatch": "HELD" if result["research_warranted"] else "NOT_REQUESTED",
            "authorization": "NON_AUTHORIZING_FIRST_APPRAISAL",
        }
        self.store.append_first_appraisal(record_id, assignment_id, bundle, "VALIDATED", merged, meta)
        return merged, meta

    def close(self) -> None:
        self.stages.close()

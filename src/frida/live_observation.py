"""Bounded, auditable live observation cycles; no decorative agents."""
from __future__ import annotations

from datetime import UTC, datetime
from collections.abc import Callable, Iterable
from uuid import uuid4

from .observation import ObservationAuditEvent, validate_and_prepare


class LiveObservationCycle:
    """Observe retained approved source snapshots and dispatch only real candidates."""
    def __init__(self, service, snapshots_provider: Callable[[], Iterable] | None = None):
        self.service = service
        self._snapshots_provider = snapshots_provider or service.store.retained_snapshots

    def run_once(self) -> dict[str, object]:
        now = datetime.now(tz=UTC)
        snapshots = tuple(self._snapshots_provider())
        assignment_id = str((self.service.store.active_assignment() or {}).get("assignment_id") or "TAIPEI_TECHNICAL_ARCHIVE")
        cycle_id = "cycle-" + uuid4().hex
        self.service.store.create_observation_cycle(cycle_id, now, len(snapshots), assignment_id)
        event = lambda kind, message, payload={}: self.service.store.append_observation_cycle_event(
            cycle_id, datetime.now(tz=UTC), kind, message, payload
        )
        event("cycle.started", "New autonomous observation cycle started", {"source_count": len(snapshots)})
        candidates = []
        semantic_calls = 0
        for snapshot in snapshots:
            if hasattr(snapshot, "persisted"):
                persisted = snapshot.persisted()
                previous = self.service.store.latest_source_fabric_observation(str(persisted["source_id"]), assignment_id)
                captured = self.service.capture_source_fabric_snapshot(persisted, previous)
                classification = captured["classification"]
                event("observe.source_examined", f"{persisted['source_id']}: official source state examined", {
                    "source_id": persisted["source_id"], "state_fingerprint": persisted["fingerprint_sha256"],
                    "classification": classification, "source_label": str(persisted.get("authority") or persisted["source_id"]),
                })
                event("pattern.assessed", f"{persisted['source_id']}: temporal evidence pattern assessed", {
                    "pattern_assessment_id": captured["pattern_assessment_id"], "state": captured["pattern_state"],
                    "authorizes_signal": False,
                })
                if classification != "SAME_STATE":
                    retained = self.service.store.latest_source_fabric_observation(str(persisted["source_id"]), assignment_id)
                    try:
                        appraisal = self.service.first_appraise_london_change(retained) if retained else None
                    except Exception as error:
                        event("first_appraisal.runtime_failed", "First Appraisal stopped before authorization", {"error_class": type(error).__name__, "semantic_calls": 1})
                        semantic_calls += 1
                    else:
                        if appraisal is not None:
                            result, meta = appraisal
                            semantic_calls += 1
                            event("first_appraisal.validated", "First Appraisal retained a non-authorizing strategic hypothesis", {
                                "strategic_interest": result["strategic_interest"], "opportunity_family": result["opportunity_family"],
                                "research_dispatch": result["research_dispatch"], "semantic_calls": 1,
                                "usage": meta.get("usage", {}), "latency_ms": meta.get("latency_ms"),
                            })
                event("triage.no_candidate", f"{persisted['source_id']}: {classification.lower()} — no semantic dispatch", {
                    "reason": classification, "semantic_calls": semantic_calls,
                })
                continue
            event("observe.source_examined", f"{snapshot.source_id}: approved source snapshot examined", {
                "source_id": snapshot.source_id, "content_hash": snapshot.content_hash,
                "source_reference": snapshot.source_reference,
            })
            # A retained identical hash is a real unchanged observation, not a new world event.
            if not self.service.store.reserve_observation(snapshot):
                self.service.store.record_audit((
                    ObservationAuditEvent("observation.received", snapshot.source_id, snapshot.content_hash),
                    ObservationAuditEvent("candidate.deduplicated", snapshot.source_id, "known_hash"),
                ))
                event("triage.no_candidate", f"{snapshot.source_id}: no new candidate — no dispatch", {
                    "reason": "unchanged_or_duplicate_hash", "semantic_calls": 0,
                })
                continue
            # This branch supports a future approved source acquisition; deterministic
            # filters run before any semantic stage and never invent relevance.
            result = validate_and_prepare(self.service.observers[snapshot.source_id], snapshot)
            self.service.store.record_audit(result.audit)
            if result.candidate_signal is None:
                event("triage.no_candidate", f"{snapshot.source_id}: deterministically filtered — no dispatch", {"reason": result.filtered_reason, "semantic_calls": 0})
            else:
                self.service.store.record_candidate(result.candidate_signal)
                candidates.append(result.candidate_signal.signal_id)
                event("candidate.detected", f"{snapshot.source_id}: candidate signal detected", {"candidate_signal_id": result.candidate_signal.signal_id})
                # Runtime dispatch is deliberately unavailable here unless an approved
                # live evidence bundle and execution authorization exist.
                event("triage.pending_authorization", "Candidate retained for governed semantic triage", {"candidate_signal_id": result.candidate_signal.signal_id})
        status = "COMPLETED_NO_DISPATCH" if not candidates else "COMPLETED_PENDING_GOVERNED_TRIAGE"
        event("cycle.completed", "Cycle completed; no semantic dispatch" if not candidates else "Cycle completed; candidate awaits governed triage", {"candidate_count": len(candidates), "semantic_calls": semantic_calls})
        self.service.store.complete_observation_cycle(cycle_id, datetime.now(tz=UTC), status, len(candidates), semantic_calls)
        return {"cycle_id": cycle_id, "status": status, "candidate_count": len(candidates), "semantic_call_count": semantic_calls}

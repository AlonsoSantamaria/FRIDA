from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep, monotonic
import unittest

from frida.accelerated_replay import AcceleratedHistoricalReplay, MODE, verify_approved_sequence
from frida.persistence import StagingStore
from frida.golden_path import ChallengerAssessment, InvestigationAnalysis, wp01_current_evidence
from frida.domain import ChallengeMateriality
from frida.case_spine import CaseSpine


ROOT = Path(__file__).parents[1] / "data" / "source-validation" / "wp01" / "denue" / "raw"


class AcceleratedHistoricalReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = StagingStore(Path(self.temp.name) / "replay.sqlite3")
        self.replay = AcceleratedHistoricalReplay(self.store, ROOT)

    def tearDown(self):
        self.store.close(); self.temp.cleanup()

    def test_approved_sequence_is_real_hash_verified_and_chronological(self):
        sequence = verify_approved_sequence(ROOT)
        self.assertEqual([item.replay_sequence for item in sequence], [1, 2])
        self.assertLess(sequence[0].source_date, sequence[1].source_date)

    def test_baseline_is_quiet_then_change_stops_at_attention_boundary(self):
        replay_id = self.replay.start("TEST_OPERATOR")
        first = self.replay.process_deterministic_snapshot(replay_id, 1, datetime(2026, 8, 27, tzinfo=UTC))
        second = self.replay.process_deterministic_snapshot(replay_id, 2, datetime(2026, 8, 27, 0, 1, tzinfo=UTC))
        self.assertEqual(first["state"], "NO_ELIGIBLE_SIGNAL")
        self.assertEqual(second["state"], "ATTENTION_PENDING")
        record = self.store.accelerated_replay(replay_id)
        self.assertEqual(record["sequence_version"], "DENUE_QRO_0525_0526_v1")
        self.assertEqual(record["snapshots"][0]["state"], "NO_ELIGIBLE_SIGNAL")
        self.assertEqual(record["snapshots"][1]["state"], "ATTENTION_PENDING")
        self.assertTrue(record["snapshots"][1]["signal_id"].startswith("signal-replay-"))
        self.assertEqual(self.store.status()["candidate_signals"], 0)
        self.assertTrue(all(event["payload"].get("execution_mode", MODE) == MODE or event["event_type"] != "replay.started" for event in record["events"]))

    def test_duplicate_start_is_rejected_and_history_is_append_only(self):
        replay_id = self.replay.start("TEST_OPERATOR")
        with self.assertRaisesRegex(ValueError, "already active"):
            self.replay.start("TEST_OPERATOR")
        self.replay.process_deterministic_snapshot(replay_id, 1)
        record = self.store.accelerated_replay(replay_id)
        self.assertEqual(len(record["events"]), 3)

    def test_later_replay_reuses_canonical_signal_but_keeps_own_audit_history(self):
        first=self.replay.start("TEST_OPERATOR")
        self.replay.process_deterministic_snapshot(first,1); initial=self.replay.process_deterministic_snapshot(first,2)
        self.store.append_accelerated_replay_event(first,"replay.stopped","test stop",{"reason":"test"})
        self.store.complete_accelerated_replay(first,"STOPPED")
        second=self.replay.start("TEST_OPERATOR")
        self.replay.process_deterministic_snapshot(second,1); replayed=self.replay.process_deterministic_snapshot(second,2)
        self.assertEqual(replayed["signal_id"],initial["signal_id"])
        self.assertIsNotNone(self.store.signal(initial["signal_id"]))
        record=self.store.accelerated_replay(second)
        self.assertEqual(record["snapshots"][1]["signal_id"],initial["signal_id"])
        self.assertTrue(record["events"][-1]["payload"]["canonical_signal_reused"])

    def test_runtime_stop_is_append_only_and_releases_active_replay(self):
        replay_id=self.replay.start("TEST_OPERATOR")
        self.replay.process_deterministic_snapshot(replay_id,1); self.replay.process_deterministic_snapshot(replay_id,2)
        self.store.append_accelerated_replay_event(replay_id,"replay.stopped","Replay stopped before runtime",{"reason":"canonical_signal_already_exists","retry_count":0})
        self.store.complete_accelerated_replay(replay_id,"STOPPED")
        record=self.store.accelerated_replay(replay_id)
        self.assertEqual(record["status"],"STOPPED")
        self.assertFalse(record["active"])
        self.assertEqual(record["events"][-1]["payload"]["reason"],"canonical_signal_already_exists")

    def test_deterministic_projection_verification_closes_without_semantic_dispatch(self):
        replay_id=self.replay.start("TEST_OPERATOR")
        self.replay.process_deterministic_snapshot(replay_id,1); self.replay.process_deterministic_snapshot(replay_id,2)
        self.replay.stop_deterministic_verification(replay_id)
        record=self.store.accelerated_replay(replay_id)
        self.assertEqual(record["status"], "STOPPED")
        self.assertFalse(record["active"])
        self.assertEqual(record["events"][-1]["payload"]["semantic_calls"], 0)

    def test_live_deterministic_progression_persists_each_transition_before_the_next(self):
        replay_id = self.replay.start_live_deterministic_progression("TEST_OPERATOR", step_seconds=.01)
        deadline = monotonic() + 1
        while self.store.accelerated_replay(replay_id)["status"] == "RUNNING" and monotonic() < deadline:
            sleep(.02)
        record = self.store.accelerated_replay(replay_id)
        self.assertEqual(record["status"], "STOPPED")
        self.assertEqual([event["event_type"] for event in record["events"]], [
            "replay.started", "observe.source_examined", "signal.none", "observe.source_examined", "signal.detected", "replay.stopped",
        ])
        self.assertTrue(all(event["payload"].get("semantic_calls", 0) == 0 for event in record["events"] if "semantic_calls" in event["payload"]))

    def test_reuse_path_reaches_the_next_model_boundary_without_invoking_a_model(self):
        first=self.replay.start("TEST_OPERATOR"); self.replay.process_deterministic_snapshot(first,1); signal=self.replay.process_deterministic_snapshot(first,2)
        CaseSpine(self.store).resolve_attention(signal["signal_id"], "INVESTIGATE", "canonical", title="Canonical", label="HISTORICAL")
        self.store.complete_accelerated_replay(first,"STOPPED")
        replay_id=self.replay.start("TEST_OPERATOR"); self.replay.process_deterministic_snapshot(replay_id,1); self.replay.process_deterministic_snapshot(replay_id,2)
        class BoundaryStages:
            def lead_attention(self,*_): raise RuntimeError("MODEL_CALL_BOUNDARY_REACHED")
            def close(self): pass
        with self.assertRaisesRegex(RuntimeError,"MODEL_CALL_BOUNDARY_REACHED"):
            self.replay.run_authorized_semantic_path(replay_id,wp01_current_evidence(datetime.now(tz=UTC)),"TEST_RUNTIME",BoundaryStages())
        record=self.store.accelerated_replay(replay_id)
        self.assertEqual(record["status"],"STOPPED")
        self.assertTrue(any(event["event_type"] == "frida.attention_reused" for event in record["events"]))

    def test_investigate_creates_candidate_only_after_attention_then_uses_option_25(self):
        class Stages:
            def __init__(self): self.calls=[]
            def _meta(self): return {"usage":{},"latency_ms":1,"configured_max_output_tokens":4096}
            def lead_attention(self,*_): self.calls.append("attention"); return {"attention":"INVESTIGATE","reason":"bounded","relevant_evidence_ids":["wp01-s1-0526"],"uncertainties":["limits"],"strategic_dimension":"directory","investigation_question":"what is supported?","claim_scope":[],"evidence_gaps":[],"selected_specialists":["economic_directory_change"],"mandates":["review"]},self._meta()
            def economic_directory_change(self,*_): self.calls.append("economic"); return InvestigationAnalysis(("directory",),("limit",),("alternative",)),self._meta()
            def lead_review(self,*_): self.calls.append("review"); return {"decision":"READY_FOR_CHALLENGE","reason":"bounded","reduced_claim_scope":[],"evidence_gap":None,"additional_specialist":None,"mandate":None},self._meta()
            def challenger(self,*_): self.calls.append("challenger"); return ChallengerAssessment(ChallengeMateriality.ADVISORY,"bounded","retain",("wp01-s1-0526",)),self._meta()
            def lead_interpretation(self,*_): self.calls.append("interpretation"); return {"decision":"RESTRICT_INTERPRETATION","supported_interpretation":["directory"],"removed_or_restricted_claims":[],"unresolved_uncertainties":["limit"]},self._meta()
        replay_id=self.replay.start("TEST_OPERATOR")
        self.replay.process_deterministic_snapshot(replay_id,1); self.replay.process_deterministic_snapshot(replay_id,2)
        stages=Stages(); result=self.replay.run_authorized_semantic_path(replay_id,wp01_current_evidence(datetime.now(tz=UTC)),"TEST_RUNTIME",stages)
        self.assertEqual(result["state"],"COMPLETED")
        self.assertEqual(stages.calls,["attention","attention","economic","review","challenger","interpretation"])
        record=self.store.accelerated_replay(replay_id)
        self.assertEqual(record["status"],"COMPLETED"); self.assertEqual(record["snapshots"][1]["attention"],"INVESTIGATE")
        self.assertTrue(record["snapshots"][1]["candidate_signal_id"])
        replay_events = [event["event_type"] for event in record["events"]]
        self.assertIn("stage.started", replay_events)
        self.assertIn("stage.model_completed", replay_events)
        self.assertIn("stage.gate_opened", replay_events)
        stage_events = [event for event in record["events"] if event["event_type"] == "stage.started"]
        self.assertTrue(stage_events[0]["payload"]["execution_id"].startswith("exec-case-"))

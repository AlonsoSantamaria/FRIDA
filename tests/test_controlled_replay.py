from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from frida.controlled_replay import (
    EXECUTION_MODE, SOURCE_OBSERVATION_MODE, new_execution,
    register_execution_attempt, verify_file_hashes,
)
from frida.controlled_replay_run import runtime_failure_payload, stopped_runtime_failure_view
from frida.demo_view import render_html
from frida.domain import EvidenceClass
from frida.golden_path import GoldenPathOrchestrator, wp01_current_evidence
from frida.observation import CandidateSignal
from frida.persistence import StagingStore


NOW = datetime(2026, 8, 23, tzinfo=UTC)
HASH = "2ea1e298086f109cdbdb6a036d6cd3ecfbdfe26123b34248d73b1d06c201304a"


def candidate() -> CandidateSignal:
    return CandidateSignal("signal-cb43c4e133eb3f1f", "DENUE", HASH, NOW, "dedup-key", "official", 2)


class ControlledReplayTests(unittest.TestCase):
    def test_multiple_execution_ids_can_reference_one_immutable_candidate(self):
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3")
            store.record_candidate(candidate())
            first = new_execution(candidate(), wp01_current_evidence(NOW), "Architecture replay authorization", NOW)
            second = new_execution(candidate(), wp01_current_evidence(NOW), "Architecture replay authorization", NOW)
            store.create_controlled_replay_execution(first.as_ledger_row())
            store.create_controlled_replay_execution(second.as_ledger_row())
            self.assertNotEqual(first.execution_id, second.execution_id)
            self.assertEqual(store.execution_attempt(first.execution_id)["candidate_signal_id"], candidate().signal_id)
            self.assertEqual(store.execution_attempt(second.execution_id)["source_observation_mode"], SOURCE_OBSERVATION_MODE)
            store.close()

    def test_execution_ledger_rejects_overwrite_and_unknown_or_new_observation_semantics(self):
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3")
            store.record_candidate(candidate())
            execution = new_execution(candidate(), wp01_current_evidence(NOW), "Architecture replay authorization", NOW)
            store.create_controlled_replay_execution(execution.as_ledger_row())
            with self.assertRaisesRegex(ValueError, "append-only"):
                store.create_controlled_replay_execution(execution.as_ledger_row())
            altered = execution.as_ledger_row()
            altered["execution_id"] = "exec-illegal"
            altered["execution_mode"] = "LIVE_WORLD_OBSERVATION"
            with self.assertRaisesRegex(ValueError, "governed"):
                store.create_controlled_replay_execution(altered)
            with self.assertRaises(Exception):
                store.record_candidate(candidate())
            self.assertEqual(store.candidate(candidate().signal_id), candidate())
            store.close()

    def test_replay_reverifies_wp01_hashes_before_registration(self):
        root = Path(__file__).resolve().parents[1]
        evidence = wp01_current_evidence(NOW)
        verify_file_hashes(root, {item.evidence_id: item.content_hash for item in evidence})
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            verify_file_hashes(root, {**{item.evidence_id: item.content_hash for item in evidence}, "wp01-s3-semaforo": "0" * 64})

    def test_registration_is_execution_only_and_never_creates_world_observation(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3")
            store.record_candidate(candidate())
            execution = new_execution(candidate(), wp01_current_evidence(NOW), "Architecture replay authorization", NOW)
            register_execution_attempt(store, execution, root)
            saved = store.execution_attempt(execution.execution_id)
            self.assertEqual(saved["execution_mode"], EXECUTION_MODE)
            self.assertEqual(saved["events"][0]["payload"]["claims_new_world_observation"], False)
            self.assertEqual(store.status()["observations"], 0)
            self.assertEqual(store.status()["candidate_signals"], 1)
            store.close()

    def test_controlled_replay_view_labels_history_and_current_execution(self):
        html = render_html({
            "run_id": "exec-1", "signal_id": candidate().signal_id, "state": "COMPLETED", "audit": [],
            "execution_mode": EXECUTION_MODE, "source_observation_mode": SOURCE_OBSERVATION_MODE,
            "original_execution_reference": "first-blocked.md", "disposition": "EVIDENCE_INSUFFICIENT",
        })
        self.assertIn("Historical real INEGI DENUE observation", html)
        self.assertIn("not a new external event", html)
        self.assertIn("immutable historical GOLDEN_PATH_BLOCKED", html)

    def test_new_execution_cannot_overwrite_historical_blocked_projection(self):
        root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3")
            historical = {"run_id": "run-signal-cb43c4e133eb3f1f", "state": "STOPPED_RUNTIME_FAILURE", "audit": [{"at": NOW.isoformat(), "stage": "semantic_triage.failed", "detail": "historical"}]}
            store.save_golden_path_view(historical)
            store.record_candidate(candidate())
            execution = new_execution(candidate(), wp01_current_evidence(NOW), "Architecture replay authorization", NOW)
            register_execution_attempt(store, execution, root)
            self.assertEqual(store.latest_golden_path_view(), historical)
            self.assertNotEqual(execution.execution_id, historical["run_id"])
            store.close()

    def test_generic_transport_failure_is_terminal_append_only_and_has_no_downstream_effects(self):
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3")
            store.record_candidate(candidate())
            execution = new_execution(candidate(), wp01_current_evidence(NOW), "Architecture replay authorization", NOW)
            store.create_controlled_replay_execution(execution.as_ledger_row())
            payload = runtime_failure_payload(ConnectionError("never persist this message"), "Semantic Triage")
            store.append_execution_event(execution.execution_id, NOW, "execution.stopped_runtime_failure", payload)
            saved = store.execution_attempt(execution.execution_id)
            self.assertEqual(saved["events"][-1]["event_type"], "execution.stopped_runtime_failure")
            self.assertEqual(saved["events"][-1]["payload"]["category"], "TRANSPORT")
            self.assertEqual(saved["events"][-1]["payload"]["retry_count"], 0)
            self.assertNotIn("message", saved["events"][-1]["payload"])
            self.assertEqual(len(saved["events"]), 1)
            self.assertIsNone(store.latest_golden_path_view())
            store.close()

    def test_runtime_failure_cannot_be_appended_after_completed_execution(self):
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3")
            store.record_candidate(candidate())
            execution = new_execution(candidate(), wp01_current_evidence(NOW), "Architecture replay authorization", NOW)
            store.create_controlled_replay_execution(execution.as_ledger_row())
            store.append_execution_event(execution.execution_id, NOW, "execution.completed", {"state": "COMPLETED"})
            with self.assertRaisesRegex(ValueError, "after a completed"):
                store.append_execution_event(execution.execution_id, NOW, "execution.stopped_runtime_failure", {"retry_count": 0})
            store.close()

    def test_failed_projection_is_separate_from_historical_execution_and_exposes_no_disposition(self):
        payload = runtime_failure_payload(ConnectionError("transport"), "Semantic Triage")
        view = stopped_runtime_failure_view("exec-new", candidate().signal_id, NOW, payload)
        self.assertEqual(view["state"], "STOPPED_RUNTIME_FAILURE")
        self.assertIsNone(view["disposition"])
        self.assertEqual(view["execution_mode"], EXECUTION_MODE)
        self.assertEqual(view["audit"][0]["metadata"]["retry_count"], 0)

    def test_transport_failure_stops_before_downstream_stages_or_disposition(self):
        calls: list[str] = []
        class TransportFailingStages:
            def triage(self, signal, evidence):
                calls.append("triage")
                raise ConnectionError("transport unavailable")
            def investigate(self, signal, evidence):
                calls.append("investigate")
                raise AssertionError("must not execute")
            def challenge(self, analysis, evidence):
                calls.append("challenge")
                raise AssertionError("must not execute")
        with self.assertRaises(ConnectionError):
            GoldenPathOrchestrator(TransportFailingStages()).run(candidate(), wp01_current_evidence(NOW), NOW)
        self.assertEqual(calls, ["triage"])

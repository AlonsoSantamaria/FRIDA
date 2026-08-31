from datetime import UTC, datetime
import unittest

from frida.domain import ChallengeMateriality, EvidenceClass, GeographicConfidence
from frida.golden_path import (
    ChallengerAssessment, GoldenPathOrchestrator, InvestigationAnalysis,
    TriageDecision, wp01_current_evidence,
)
from frida.observation import DenueObserver, ReplaySnapshot, validate_and_prepare
from frida.golden_path_run import approved_observation, runtime_failure_view
from frida.adk_runtime import (
    MODEL, AdkTaskTerminalError, sanitized_event_shape, sanitized_usage_metadata,
    task_completion_instruction,
)


NOW = datetime(2026, 8, 23, tzinfo=UTC)


class FakeStages:
    def triage(self, signal, evidence):
        return TriageDecision(True, "A corrected public edition changed.", tuple(x.evidence_id for x in evidence[:2]), ("Directory changes are not openings.",))
    def investigate(self, signal, evidence):
        return InvestigationAnalysis(("Public records merit bounded review.",), ("WP01 geography remains unresolved.",), ("Directory-update bias may explain the change.",))
    def challenge(self, analysis, evidence):
        return ChallengerAssessment(ChallengeMateriality.MATERIAL, "S3 text cannot prove corridor precision.", "reduce_confidence", ("wp01-s3-semaforo",))


class GoldenPathLocalTests(unittest.TestCase):
    def test_runtime_model_baseline_is_gemini_36_flash(self):
        self.assertEqual(MODEL, "gemini-3.6-flash")

    def signal(self):
        snapshot = ReplaySnapshot("DENUE", "data/source-validation/wp01/denue/raw/denue_22_0526_corrected_csv.zip", NOW,
            "2ea1e298086f109cdbdb6a036d6cd3ecfbdfe26123b34248d73b1d06c201304a", EvidenceClass.REAL, 2, NOW)
        return validate_and_prepare(DenueObserver(), snapshot).candidate_signal

    def test_observation_led_path_ends_in_governed_insufficiency(self):
        run = GoldenPathOrchestrator(FakeStages()).run(self.signal(), wp01_current_evidence(NOW), NOW)
        self.assertEqual(run.state, "COMPLETED")
        self.assertEqual(run.disposition.value, "EVIDENCE_INSUFFICIENT")
        self.assertEqual(run.audit[0]["stage"], "observation.accepted")
        self.assertFalse(run.disposition_factors["geographic_precision"])

    def test_critical_challenge_stops_without_disposition(self):
        class Critical(FakeStages):
            def challenge(self, analysis, evidence):
                return ChallengerAssessment(ChallengeMateriality.CRITICAL, "provenance gap", "stop", ("wp01-s3-semaforo",))
        run = GoldenPathOrchestrator(Critical()).run(self.signal(), wp01_current_evidence(NOW), NOW)
        self.assertEqual(run.state, "STOPPED_CRITICAL_CHALLENGE")
        self.assertIsNone(run.disposition)

    def test_current_wp01_bundle_preserves_real_hashes_and_geographic_limits(self):
        bundle = wp01_current_evidence(NOW)
        self.assertEqual({item.evidence_class for item in bundle}, {EvidenceClass.REAL})
        self.assertIn(GeographicConfidence.UNRESOLVED, {item.geographic_confidence for item in bundle})
        self.assertTrue(all(len(item.content_hash) == 64 for item in bundle))

    def test_approved_trigger_is_the_corrected_denue_edition(self):
        snapshot = approved_observation(NOW)
        self.assertEqual(snapshot.source_id, "DENUE")
        self.assertEqual(snapshot.replay_sequence, 2)
        self.assertEqual(snapshot.content_hash, "2ea1e298086f109cdbdb6a036d6cd3ecfbdfe26123b34248d73b1d06c201304a")

    def test_task_instruction_explicitly_requires_finish_task_and_all_schema_fields(self):
        instruction = task_completion_instruction("Semantic Triage", {
            "warrants_investigation": "boolean", "reason": "string",
            "relevant_evidence_ids": "array[string]", "uncertainties": "array[string]",
        })
        self.assertIn("finish_task", instruction)
        self.assertIn("exactly once", instruction)
        self.assertIn("warrants_investigation", instruction)
        self.assertIn("only permitted completion", instruction)
        self.assertIn("Do not ask questions", instruction)

    def test_terminal_error_preserves_safe_failure_phase_and_usage(self):
        error = AdkTaskTerminalError("Semantic Triage", {
            "failure_phase": "BEFORE_FINISH_TASK", "usage": {"prompt_token_count": 12},
            "finish_task_called": False, "terminal_output_present": False,
        })
        self.assertEqual(error.diagnostic["failure_phase"], "BEFORE_FINISH_TASK")
        self.assertEqual(error.diagnostic["usage"]["prompt_token_count"], 12)

    def test_future_terminal_failure_view_is_auditable_without_model_text(self):
        view = runtime_failure_view("signal-new", NOW, {"failure_phase": "BEFORE_FINISH_TASK", "usage": {"total_token_count": 9}})
        self.assertEqual(view["state"], "STOPPED_RUNTIME_FAILURE")
        self.assertEqual(view["audit"][0]["metadata"]["failure_phase"], "BEFORE_FINISH_TASK")

    def test_sanitized_future_event_diagnostic_has_mechanics_not_model_content(self):
        class Call: name = "finish_task"
        class Part:
            text = "do not persist this"
            function_call = None
            function_response = None
        class Content: parts = [Part()]
        class Event:
            content = Content(); finish_reason = "STOP"; turn_complete = True
            turn_complete_reason = "done"; output = None
            def get_function_calls(self): return [Call()]
            def get_function_responses(self): return []
            def is_final_response(self): return True
        shape = sanitized_event_shape(Event())
        self.assertEqual(shape["content_part_kinds"], ["text"])
        self.assertEqual(shape["function_calls"], ["finish_task"])
        self.assertNotIn("do not persist this", str(shape))

    def test_sanitized_usage_preserves_returned_categories_only(self):
        class Usage:
            def model_dump(self, exclude_none):
                return {"prompt_token_count": 10, "thoughts_token_count": 4,
                        "total_token_count": 14, "prompt_tokens_details": ["not persisted"]}
        self.assertEqual(sanitized_usage_metadata(Usage()), {
            "prompt_token_count": 10, "thoughts_token_count": 4, "total_token_count": 14,
        })

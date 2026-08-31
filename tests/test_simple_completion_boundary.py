"""Deterministic validation of the simple provider completion envelope."""
from __future__ import annotations

import importlib.util
import json
import unittest

PYDANTIC_AVAILABLE = importlib.util.find_spec("pydantic") is not None


@unittest.skipUnless(PYDANTIC_AVAILABLE, "requires the declared pydantic runtime dependency")
class SimpleCompletionBoundaryTests(unittest.TestCase):
    allowed = {"wp01-s1-0525", "wp01-s1-0526", "wp01-s2-felix", "wp01-s3-semaforo"}

    def setUp(self):
        from frida.semantic_completion import SemanticCompletionValidationError
        self.error = SemanticCompletionValidationError

    @staticmethod
    def envelope(value):
        return {"result_json": json.dumps(value)}

    def test_triage_valid_json_preserves_authoritative_domain_result(self):
        from frida.semantic_completion import parse_triage_completion
        result = parse_triage_completion(self.envelope({
            "warrants_investigation": True, "reason": "bounded signal",
            "relevant_evidence_ids": ["wp01-s1-0526"], "uncertainties": ["directory change"],
        }), self.allowed)
        self.assertTrue(result.warrants_investigation)
        self.assertEqual(result.relevant_evidence_ids, ("wp01-s1-0526",))

    def test_investigation_valid_json_preserves_authoritative_domain_result(self):
        from frida.semantic_completion import parse_investigation_completion
        result = parse_investigation_completion(self.envelope({
            "claims": ["bounded claim"], "limitations": ["no point precision"],
            "alternative_explanations": ["directory update"],
        }), self.allowed)
        self.assertEqual(result.claims, ("bounded claim",))

    def test_challenger_valid_json_preserves_authoritative_domain_result(self):
        from frida.domain import ChallengeMateriality
        from frida.semantic_completion import parse_challenger_completion
        result = parse_challenger_completion(self.envelope({
            "materiality": "MATERIAL", "reason": "geography limited", "required_effect": "downgrade",
            "evidence_ids": ["wp01-s3-semaforo"],
        }), self.allowed)
        self.assertEqual(result.materiality, ChallengeMateriality.MATERIAL)

    def test_invalid_json_non_object_prose_and_schema_defects_fail_closed(self):
        from frida.semantic_completion import parse_triage_completion
        invalid = [
            {"result_json": "not json"}, {"result_json": "[]"},
            self.envelope({"warrants_investigation": True}),
            self.envelope({"warrants_investigation": "true", "reason": "x", "relevant_evidence_ids": ["wp01-s1-0526"], "uncertainties": ["u"]}),
            self.envelope({"warrants_investigation": True, "reason": "x", "relevant_evidence_ids": ["wp01-s1-0526"], "uncertainties": ["u"], "extra": "forbidden"}),
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(self.error):
                parse_triage_completion(value, self.allowed)

    def test_invalid_materiality_and_unapproved_evidence_fail_closed(self):
        from frida.semantic_completion import parse_challenger_completion
        for value in (
            {"materiality": "HIGH", "reason": "x", "required_effect": "stop", "evidence_ids": ["wp01-s1-0526"]},
            {"materiality": "MATERIAL", "reason": "x", "required_effect": "stop", "evidence_ids": ["not-approved"]},
        ):
            with self.subTest(value=value), self.assertRaises(self.error):
                parse_challenger_completion(self.envelope(value), self.allowed)

    def test_no_coercion_or_plain_prose_fallback(self):
        from frida.semantic_completion import parse_investigation_completion
        with self.assertRaises(self.error):
            parse_investigation_completion({"result_json": "A useful conclusion."}, self.allowed)
        with self.assertRaises(self.error):
            parse_investigation_completion(self.envelope({
                "claims": "not a list", "limitations": ["x"], "alternative_explanations": ["y"],
            }), self.allowed)

    def test_validation_failure_has_no_downstream_stage_or_disposition_path(self):
        from datetime import UTC, datetime
        from frida.golden_path import GoldenPathOrchestrator, wp01_current_evidence
        from frida.observation import DenueObserver, ReplaySnapshot, validate_and_prepare
        from frida.domain import EvidenceClass
        from frida.semantic_completion import parse_triage_completion

        now = datetime(2026, 8, 24, tzinfo=UTC)
        class FailingStages:
            metrics = {}
            investigate_called = False
            challenge_called = False
            def triage(self, signal, evidence):
                return parse_triage_completion({"result_json": "plain prose"}, {x.evidence_id for x in evidence})
            def investigate(self, signal, evidence):
                self.investigate_called = True
            def challenge(self, analysis, evidence):
                self.challenge_called = True

        snapshot = ReplaySnapshot("DENUE", "historical", now, "a" * 64, EvidenceClass.REAL, 1, now)
        signal = validate_and_prepare(DenueObserver(), snapshot).candidate_signal
        stages = FailingStages()
        with self.assertRaises(self.error):
            GoldenPathOrchestrator(stages).run(signal, wp01_current_evidence(now), now)
        self.assertFalse(stages.investigate_called)
        self.assertFalse(stages.challenge_called)

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from frida.case_presentation import lead_case, water_case
from frida.case_spine import CaseSpine, evidence_bundle
from frida.domain import EvidenceClass
from frida.golden_path import wp01_current_evidence
from frida.golden_path import ChallengerAssessment, InvestigationAnalysis
from frida.domain import ChallengeMateriality
from frida.lead_runtime import execute_lead_case
from frida.observation import ReplaySnapshot
from frida.persistence import StagingStore
from frida.demo_view import render_case_presentation_html, render_shell, render_wow_action_html


def snapshot(hash_value: str, evidence_class=EvidenceClass.REAL):
    now=datetime.now(tz=UTC)
    return ReplaySnapshot("DENUE", "official-source", now, hash_value, evidence_class, 1, now)


class GenericCaseSpineTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.store=StagingStore(Path(self.temp.name)/"frida.sqlite3"); self.spine=CaseSpine(self.store)
    def tearDown(self): self.store.close(); self.temp.cleanup()

    def test_signal_is_not_candidate_and_watch_persists_without_candidate(self):
        observed=self.spine.observe(snapshot("a"*64))
        self.assertEqual(observed["state"], "ATTENTION_PENDING"); self.assertIsNone(observed["candidate_signal"])
        result=self.spine.resolve_attention(observed["signal_id"], "WATCH", "bounded change retained", title="x", label="x")
        self.assertEqual(result["attention"], "WATCH"); self.assertIsNone(result["candidate_signal"])
        self.assertEqual(self.store.status()["candidate_signals"], 0)

    def test_ignore_creates_no_candidate_and_investigate_creates_linked_case(self):
        ignored=self.spine.observe(snapshot("b"*64)); self.spine.resolve_attention(ignored["signal_id"], "IGNORE", "outside approved scope", title="x", label="x")
        observed=self.spine.observe(snapshot("c"*64)); result=self.spine.resolve_attention(observed["signal_id"], "INVESTIGATE", "approved evidence warrants review", title="Generic case", label="OBSERVED")
        self.assertIsNotNone(result["candidate_signal"]); case=self.store.case(result["case_id"])
        self.assertEqual({link["link_type"] for link in case["links"]}, {"SIGNAL", "CANDIDATE"})

    def test_canonical_attention_and_candidate_are_reused_without_competing_rows(self):
        observed=self.spine.observe(snapshot("f"*64))
        first=self.spine.resolve_attention(observed["signal_id"], "INVESTIGATE", "approved", title="First", label="HISTORICAL")
        second=self.spine.resolve_attention(observed["signal_id"], "INVESTIGATE", "approved", title="Second", label="REPLAY")
        self.assertEqual(first["candidate_signal"].signal_id, second["candidate_signal"].signal_id)
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.spine.resolve_attention(observed["signal_id"], "WATCH", "conflict", title="Bad", label="REPLAY")

    def test_bundle_and_execution_identity_are_generic_and_append_only(self):
        observed=self.spine.observe(snapshot("d"*64)); result=self.spine.resolve_attention(observed["signal_id"], "INVESTIGATE", "approved", title="Generic case", label="OBSERVED")
        evidence=wp01_current_evidence(datetime.now(tz=UTC)); bundle=evidence_bundle(result["case_id"], evidence)
        execution=self.spine.register_execution(result["case_id"], result["candidate_signal"], evidence, "TEST_AUTH")
        record=self.store.execution_attempt(execution)
        self.assertTrue(record["generic_case_execution"]); self.assertEqual(record["case_id"], result["case_id"])
        self.assertEqual(len(record["evidence_hashes"]), len(evidence))
        self.store.persist_evidence_bundle(bundle)
        with self.assertRaises(ValueError): self.store.persist_evidence_bundle(bundle)

    def test_one_template_renders_water_and_lead_cases_without_fabrication(self):
        water=water_case({"execution_id":"water-run", "selected":{"case_id":"water-case", "measure":"observed availability", "geography":"Qro", "fact_ids":["F1"], "source_ids":["S1"]}, "assessment":{"limitations":["bounded"]}, "governance":{"outcome":"RESTRICTED"}})
        lead=lead_case({"execution_id":"lead-run", "case":{"case_id":"lead-case", "title":"Directory condition", "label":"HISTORICAL", "case_mode":"CONTROLLED_REPLAY", "source_observation_mode":"HISTORICAL_REAL"}, "rows":[], "catalogue":[], "totals":{}, "attention":"INVESTIGATE", "disposition":"EVIDENCE_INSUFFICIENT"})
        self.assertIn("water-case", render_case_presentation_html(water)); self.assertIn("lead-case", render_case_presentation_html(lead))

    def test_case_presentation_keeps_fact_interpretation_and_recommendation_distinct(self):
        case = {
            "case_id": "case-so-what", "execution_id": "execution-so-what", "label": "OBSERVED",
            "title": "A governed case", "source": "Retained evidence", "attention": "INVESTIGATE",
            "question": "What changed?", "disposition": "EVIDENCE_INSUFFICIENT", "challenger": "ADVISORY",
            "interpretation": "RESTRICT_INTERPRETATION", "evidence_ids": [], "limitations": [], "specialists": [],
            "strategic": {"noticed": "Observed fact.", "why": "Governed interpretation.", "now": "Request specific evidence.", "limitations": ["No point precision."]},
        }
        html = render_case_presentation_html(case)
        for label in ("WHAT FRIDA NOTICED", "WHY FRIDA THINKS IT MATTERS", "WHAT FRIDA RECOMMENDS NOW"):
            self.assertIn(label, html)
        self.assertIn("Observed fact.", html)
        self.assertIn("Governed interpretation.", html)
        self.assertIn("Request specific evidence.", html)

    def test_case_return_navigation_preserves_the_visitor_origin(self):
        case = {
            "case_id": "case-navigation", "execution_id": "execution-navigation",
            "label": "OBSERVED", "title": "A governed case", "source": "Retained evidence",
            "attention": "WATCH", "question": "What changed?", "disposition": "WATCH",
            "challenger": "ADVISORY", "interpretation": "Bounded", "evidence_ids": [],
            "limitations": [], "specialists": [], "glass_hood_url": "/glass-hood?execution_id=test",
        }
        from_action = render_case_presentation_html(case, "action")
        from_history = render_case_presentation_html(case, "history")
        self.assertEqual(2, from_action.count("← BACK TO FRIDA"))
        self.assertIn("href='/'", from_action)
        self.assertIn("/foresight?execution_id=test", from_action)
        self.assertEqual(2, from_history.count("← BACK TO HISTORY"))
        self.assertIn("href='/history'", from_history)
        self.assertIn("case-top", from_action)
        self.assertIn("case-bottom", from_action)

    def test_action_shell_marks_case_links_with_their_action_origin(self):
        shell = render_shell("<main><a href='/case?case_id=case-1'>Case</a></main>", "action")
        self.assertIn("url.searchParams.set('from','action')", shell)
        self.assertIn(".metrics{margin-top:12px}", shell)

    def test_city_activity_rows_open_the_case_not_the_technical_engine(self):
        action = render_wow_action_html(
            [{"case_id": "case-1", "title": "Case", "source": "Source", "disposition": "WATCH"}],
            {"events": [{"occurred_at": "2026-08-28T12:00:00Z", "event_type": "signal.detected"}]},
        )
        self.assertIn("href='/case?case_id=case-1'", action)
        self.assertNotIn("href='/glass-hood?replay_id=", action)

    def test_generic_case_uses_the_existing_option_25_runtime(self):
        class Stages:
            def _meta(self): return {"usage": {}, "latency_ms": 1}
            def lead_attention(self,*_): return {"attention":"INVESTIGATE","reason":"bounded","relevant_evidence_ids":["wp01-s1-0526"],"uncertainties":[],"strategic_dimension":"directory","investigation_question":"what?","claim_scope":[],"evidence_gaps":[],"selected_specialists":["economic_directory_change"],"mandates":["review"]}, self._meta()
            def economic_directory_change(self,*_): return InvestigationAnalysis(("directory",),("limit",),("alternative",)), self._meta()
            def lead_review(self,*_): return {"decision":"READY_FOR_CHALLENGE","reason":"bounded","reduced_claim_scope":[],"evidence_gap":None,"additional_specialist":None,"mandate":None}, self._meta()
            def challenger(self,*_): return ChallengerAssessment(ChallengeMateriality.ADVISORY,"bounded","retain",("wp01-s1-0526",)), self._meta()
            def lead_interpretation(self,*_): return {"decision":"RESTRICT_INTERPRETATION","supported_interpretation":[],"removed_or_restricted_claims":[],"unresolved_uncertainties":[]}, self._meta()
        observed=self.spine.observe(snapshot("e"*64)); result=self.spine.resolve_attention(observed["signal_id"], "INVESTIGATE", "approved", title="Generic", label="OBSERVED")
        execution, outcome=execute_lead_case(self.store, result["case_id"], result["candidate_signal"], wp01_current_evidence(datetime.now(tz=UTC)), "TEST_AUTH", Stages())
        self.assertEqual(outcome["state"], "COMPLETED")
        record=self.store.execution_attempt(execution)
        self.assertTrue(record["generic_case_execution"])
        self.assertIn("candidate.authorized", [event["event_type"] for event in record["events"]])

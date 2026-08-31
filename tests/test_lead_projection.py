from __future__ import annotations

import unittest

from frida.demo_view import render_lead_glass_hood_html
from frida.lead_projection import build_lead_execution_projection, raw_governed_record_projection


def event(at, kind, payload): return {"occurred_at": at, "event_type": kind, "payload": payload}


class LeadProjectionTests(unittest.TestCase):
    def setUp(self):
        self.record={"execution_id":"verified", "events":[
            event("2026-08-26T02:24:57+00:00","execution.registered",{}),
            event("2026-08-26T02:24:57+00:00","execution.started",{"architecture":"REVISED_TARGET_B_OPTION_2_5"}),
            event("2026-08-26T02:24:58+00:00","signal.historical_reference_confirmed",{}),
            event("2026-08-26T02:25:01+00:00","stage.started",{"stage":"economic_directory_change"}),
            event("2026-08-26T02:25:02+00:00","stage.started",{"stage":"urban_development_status"}),
            event("2026-08-26T02:25:03+00:00","stage.model_completed",{"stage":"FRIDA Attention & Initial Plan","usage":{"prompt_token_count":1,"thoughts_token_count":2,"candidates_token_count":3,"total_token_count":6},"latency_ms":7}),
            event("2026-08-26T02:25:04+00:00","stage.semantic_artifact_persisted",{"stage":"FRIDA Attention & Initial Plan","artifact":{"attention":"INVESTIGATE","selected_specialists":["economic_directory_change","urban_development_status"],"mandates":["DENUE","status"],"relevant_evidence_ids":["one"]}}),
            event("2026-08-26T02:25:05+00:00","stage.semantic_artifact_persisted",{"stage":"economic_directory_change","artifact":{},"approved_evidence_ids":["one"]}),
            event("2026-08-26T02:25:06+00:00","stage.semantic_artifact_persisted",{"stage":"urban_development_status","artifact":{},"approved_evidence_ids":["one"]}),
            event("2026-08-26T02:25:07+00:00","stage.semantic_artifact_persisted",{"stage":"FRIDA Evidence Review","artifact":{"decision":"READY_FOR_CHALLENGE"}}),
            event("2026-08-26T02:25:08+00:00","stage.semantic_artifact_persisted",{"stage":"Independent Challenger","artifact":{"evidence_ids":["one"],"materiality":"MATERIAL"}}),
            event("2026-08-26T02:25:09+00:00","stage.semantic_artifact_persisted",{"stage":"FRIDA Post-Challenge Interpretation","artifact":{"decision":"RESTRICT_INTERPRETATION"}}),
            event("2026-08-26T02:25:10+00:00","disposition.completed",{"disposition":"EVIDENCE_INSUFFICIENT"}),
            event("2026-08-26T02:25:11+00:00","execution.completed",{}),
            event("2026-08-26T02:25:12+00:00","execution.stopped_runtime_failure",{}),
            event("2026-08-26T02:25:13+00:00","execution.audit_correction",{"authoritative_state":"COMPLETED"}),
        ]}

    def test_projection_uses_completed_facts_and_audit_correction(self):
        view=build_lead_execution_projection(self.record)
        self.assertEqual(view["status"],"COMPLETED")
        self.assertEqual(view["attention"],"INVESTIGATE")
        self.assertEqual(view["disposition"],"EVIDENCE_INSUFFICIENT")
        self.assertEqual(view["totals"]["total"],6)
        self.assertIsNotNone(view["audit_correction"])
        self.assertNotIn("execution.stopped_runtime_failure", str(view["rows"]))

    def test_html_distinguishes_actors_and_never_exposes_thought_content(self):
        html=render_lead_glass_hood_html(build_lead_execution_projection(self.record))
        self.assertIn("FRIDA",html); self.assertIn("INDEPENDENT CHALLENGER",html); self.assertIn("GOVERNANCE",html)
        self.assertIn("CUESTIONAMIENTO SIGNIFICATIVO",html)
        self.assertIn("Audit correction retained",html)
        self.assertIn("FRIDA · MUNICIPAL STRATEGIC INTELLIGENCE", html)
        self.assertIn("← BACK TO FRIDA", html)
        self.assertIn("UNDER THE HOOD", html)
        self.assertIn("ACCELERATED HISTORICAL REPLAY", html)
        self.assertIn("VIEW RAW GOVERNED RECORD", html)
        self.assertIn("href='/technical-record?execution_id=verified'", html)
        self.assertIn("height:540px;overflow-y:auto", html)
        self.assertNotIn("chain-of-thought",html.lower())

    def test_raw_record_is_reconstructed_from_the_canonical_execution_projection(self):
        class Store:
            def lead_execution_records(self):
                return [self.record]
            record = self.record
        raw = raw_governed_record_projection(Store())
        self.assertEqual("verified", raw["run_id"])
        self.assertEqual("CONTROLLED_REPLAY_DEMO", raw["execution_mode"])
        self.assertEqual("GOVERNED_SIGNAL", raw["signal_id"])
        self.assertEqual("EVIDENCE_INSUFFICIENT", raw["disposition"])
        self.assertTrue(raw["audit"])

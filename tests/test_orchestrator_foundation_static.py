import unittest

try:
    import google.adk  # noqa: F401
    from frida.orchestrator_foundation import (
        FORESIGHT_CONTRACT_STATUS, build_frida_workflow_foundation,
        challenger_gate, investigation_gate, triage_gate,
    )
    from frida.semantic_completion import TriageCompletion
except ImportError:
    google_adk_available = False
else:
    google_adk_available = True


@unittest.skipUnless(google_adk_available, "requires isolated ADK runtime")
class OrchestratorFoundationStaticTests(unittest.TestCase):
    def test_root_and_staff_are_native_single_turn_without_tools(self):
        root, staff = build_frida_workflow_foundation()
        self.assertEqual(root.name, "frida_strategic_orchestrator")
        self.assertEqual(set(staff), {"semantic_triage", "investigation", "independent_challenger"})
        self.assertTrue(all(agent.mode == "single_turn" and agent.tools == [] for agent in staff.values()))
        self.assertEqual(staff["semantic_triage"].output_schema.__name__, "TriageCompletion")
        self.assertEqual(staff["investigation"].output_schema.__name__, "InvestigationCompletion")
        self.assertEqual(staff["independent_challenger"].output_schema.__name__, "ChallengerCompletion")

    def test_gates_fail_closed_and_foresight_is_reserved(self):
        valid = TriageCompletion(warrants_investigation=True, reason="r", relevant_evidence_ids=["e"], uncertainties=["u"])
        denied = TriageCompletion(warrants_investigation=False, reason="r", relevant_evidence_ids=["e"], uncertainties=["u"])
        self.assertTrue(triage_gate(valid).allowed)
        self.assertFalse(triage_gate(denied).allowed)
        self.assertFalse(triage_gate(None).allowed)
        self.assertFalse(investigation_gate(None).allowed)
        self.assertFalse(challenger_gate(None).allowed)
        self.assertEqual(FORESIGHT_CONTRACT_STATUS, "FORESIGHT_CONTRACT_REQUIRED")

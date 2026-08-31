"""Static native structured-output specialist checks; no runtime calls."""
import importlib.util
import unittest

ADK_AVAILABLE = importlib.util.find_spec("google.adk") is not None

@unittest.skipUnless(ADK_AVAILABLE, "requires isolated Gate 4B ADK environment")
class NativeSpecialistStaticTests(unittest.TestCase):
    def test_native_staff_has_exact_schemas_and_no_completion_tools(self):
        from frida.adk_runtime import build_native_specialists
        staff = build_native_specialists()
        expected = {"semantic_triage": "TriageCompletion", "investigation": "InvestigationCompletion", "independent_challenger": "ChallengerCompletion"}
        for name, schema in expected.items():
            self.assertEqual(staff[name].mode, "single_turn")
            self.assertEqual(staff[name].output_schema.__name__, schema)
            self.assertEqual(staff[name].tools, [])
            self.assertNotIn("finish_task", staff[name].instruction)

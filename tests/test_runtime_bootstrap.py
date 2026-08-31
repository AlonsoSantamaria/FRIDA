import os
import unittest
from unittest.mock import patch
from frida.runtime_bootstrap import CONFIG,PROJECT,LOCATION,apply,environment,preflight
class RuntimeBootstrapTests(unittest.TestCase):
 def test_shared_context_is_canonical_for_all_local_flows(self):
  value=environment(); self.assertEqual(value["GOOGLE_CLOUD_PROJECT"],PROJECT); self.assertEqual(value["GOOGLE_CLOUD_LOCATION"],LOCATION); self.assertEqual(value["GOOGLE_GENAI_USE_VERTEXAI"],"TRUE")
 def test_apply_requires_no_human_export(self):
  with patch.dict(os.environ,{},clear=True): self.assertEqual(apply()["CLOUDSDK_CONFIG"],str(CONFIG)); self.assertEqual(os.environ["GOOGLE_CLOUD_PROJECT"],PROJECT)
 def test_missing_context_stops_before_adc_or_model(self):
  with patch("frida.runtime_bootstrap.CONFIG",CONFIG / "missing"):
   result=preflight(); self.assertEqual(result.state,"AUTH_CONTEXT_UNAVAILABLE"); self.assertFalse(result.checks["adc"])
 def test_no_secret_path_is_logged(self): self.assertNotIn("GOOGLE_APPLICATION_CREDENTIALS",environment())

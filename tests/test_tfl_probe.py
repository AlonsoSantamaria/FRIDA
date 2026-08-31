from __future__ import annotations

import unittest

from frida.tfl_probe import TFL_VICTORIA_STATUS_URL, probe_victoria_line


class TfLProbeTests(unittest.TestCase):
    def test_probe_normalizes_one_official_line_without_personal_data(self):
        def fetch(url):
            self.assertEqual(url, TFL_VICTORIA_STATUS_URL)
            return 200, {"X-RateLimit-Limit": "500"}, [{"id": "victoria", "name": "Victoria", "modified": "2026-08-29T10:00:00Z", "lineStatuses": [{"statusSeverity": 10, "statusSeverityDescription": "Good Service"}]}]
        result = probe_victoria_line(fetch=fetch)
        self.assertEqual(result["http_status"], 200)
        self.assertEqual(result["normalized_state"]["status"], "Good Service")
        self.assertEqual(result["credential_mode"], "ANONYMOUS_BOUNDED_PROBE")
        self.assertFalse(result["personal_data_processed"])
        self.assertEqual(result["model_calls"], 0)

    def test_registered_key_is_used_only_as_request_configuration(self):
        def fetch(url):
            self.assertIn("app_key=not-a-real-key", url)
            return 200, {}, [{"id": "victoria", "lineStatuses": [{"statusSeverityDescription": "Good Service"}]}]
        self.assertEqual(probe_victoria_line("not-a-real-key", fetch=fetch)["credential_mode"], "REGISTERED_KEY")

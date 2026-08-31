from __future__ import annotations

from datetime import UTC, datetime
import unittest

from frida.london_safety import LONDON_SAFETY_MPS, normalize_mps_borough_csv


class LondonSafetyTests(unittest.TestCase):
    def test_aggregate_borough_normalizer_excludes_retrieval_time_from_state(self):
        payload = b"Group,SubGroup,BOCU,202604,202605,202606\nTHEFT,THEFT,Wandsworth,1,2,3\nTHEFT,THEFT,Lambeth,4,5,6\nVIOLENCE,OTHER,Lambeth,2,2,2\n"
        first = normalize_mps_borough_csv(payload, retrieved_at=datetime(2026, 8, 1, tzinfo=UTC))
        second = normalize_mps_borough_csv(payload, retrieved_at=datetime(2026, 8, 2, tzinfo=UTC))
        self.assertEqual(first.source_id, LONDON_SAFETY_MPS)
        self.assertEqual(first.fingerprint_sha256, second.fingerprint_sha256)
        theft = next(item for item in first.canonical_state["groups"] if item["group"] == "THEFT")
        self.assertEqual(theft["combined_total"], 21)
        self.assertIn("not be used for predictive policing", first.canonical_state["limitations"][1])


if __name__ == "__main__":
    unittest.main()

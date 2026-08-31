from __future__ import annotations

import unittest

from frida.temporal_pattern_memory import assess


class TemporalPatternMemoryTests(unittest.TestCase):
    def test_ordinary_observation_has_no_pattern(self):
        self.assertEqual(assess(({"source_observation_id":"o1","source_id":"rain","classification":"ORDINARY_CHANGE"},)).state, "NO_PATTERN")

    def test_repetition_is_evidence_not_a_signal(self):
        rows=tuple({"source_observation_id":f"o{i}","source_id":"rain","classification":"ORDINARY_CHANGE"} for i in range(2))
        self.assertEqual(assess(rows).state, "REPEATED")

    def test_persistence_requires_multiple_changed_observations(self):
        rows=tuple({"source_observation_id":f"o{i}","source_id":"rain","classification":"ORDINARY_CHANGE"} for i in range(3))
        self.assertEqual(assess(rows).state, "PERSISTENT")

    def test_independent_sources_can_form_cross_source_pattern(self):
        rows=({"source_observation_id":"o1","source_id":"rain","classification":"ORDINARY_CHANGE","geography":"Taipei City"},{"source_observation_id":"o2","source_id":"drainage","classification":"ORDINARY_CHANGE","geography":"Taipei City"})
        self.assertEqual(assess(rows).state, "CROSS_SOURCE_PATTERN")

    def test_incompatible_geographies_do_not_form_cross_source_pattern(self):
        rows=({"source_observation_id":"o1","source_id":"rain","classification":"ORDINARY_CHANGE","geography":"Taipei City"},{"source_observation_id":"o2","source_id":"drainage","classification":"ORDINARY_CHANGE","geography":"London"})
        self.assertEqual(assess(rows).state, "NO_PATTERN")

    def test_same_state_is_not_counted_as_change(self):
        rows=tuple({"source_observation_id":f"o{i}","source_id":"rain","classification":"SAME_STATE"} for i in range(5))
        self.assertEqual(assess(rows).state, "NO_PATTERN")


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import unittest

from frida.foresight_ingestion import (
    ASSUMPTIONS, BUNDLE_ID, COMPUTATION_MODE, HORIZON, SCENARIO_INPUT_SET_ID,
    SOURCE_STATE_ID, build_scenario_input_set, evaluate_eligibility,
    ingest_water_resilience_bundle,
)
from frida.persistence import StagingStore


ROOT = Path(__file__).parents[1] / "data" / "foresight-evidence" / "water-resilience-v1"


class ForesightIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.store = StagingStore(Path(self.temp.name) / "foresight.sqlite3")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_integrity_validated_bundle_creates_eligible_append_only_state(self):
        state, input_set, decision = ingest_water_resilience_bundle(self.store, ROOT)
        self.assertTrue(state["integrity_verified"])
        self.assertEqual(state["bundle_id"], BUNDLE_ID)
        self.assertEqual(input_set["scenario_input_set_id"], SCENARIO_INPUT_SET_ID)
        self.assertEqual(decision["status"], "ELIGIBLE")
        self.assertEqual(self.store.foresight_source_state(SOURCE_STATE_ID)["facts"][3]["fact_id"], "FW-OBS-004")

    def test_hash_failure_fails_closed_before_any_persistence(self):
        with TemporaryDirectory() as copied:
            copied_root = Path(copied) / "bundle"
            shutil.copytree(ROOT, copied_root)
            (copied_root / "raw" / "conagua_dr_2201_2024.pdf").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "integrity"):
                ingest_water_resilience_bundle(self.store, copied_root)
        count = self.store.connection.execute("SELECT COUNT(*) FROM foresight_source_states").fetchone()[0]
        self.assertEqual(count, 0)

    def test_source_state_and_input_set_are_append_only(self):
        ingest_water_resilience_bundle(self.store, ROOT)
        with self.assertRaisesRegex(ValueError, "append-only"):
            ingest_water_resilience_bundle(self.store, ROOT)

    def test_scenario_definitions_have_all_frozen_variants(self):
        input_set = build_scenario_input_set(SOURCE_STATE_ID)
        self.assertEqual({item["variant"] for item in input_set["scenario_definitions"]}, {"BASELINE", "STRESS", "MITIGATION"})
        self.assertEqual(input_set["horizon"], HORIZON)
        self.assertEqual(input_set["computation_mode"], COMPUTATION_MODE)

    def test_future_conditions_are_assumptions_not_observations(self):
        self.assertEqual({item.classification for item in ASSUMPTIONS}, {"ASSUMED"})

    def test_invalid_source_integrity_is_not_eligible(self):
        state = {"source_state_id": SOURCE_STATE_ID, "bundle_id": BUNDLE_ID, "integrity_verified": False}
        decision = evaluate_eligibility(state, build_scenario_input_set(SOURCE_STATE_ID))
        self.assertEqual(decision["status"], "NOT_ELIGIBLE")
        self.assertIn("SOURCE_HASH_OR_PROVENANCE_INVALID", decision["reasons"])

    def test_wrong_geography_fails_closed(self):
        state = {"source_state_id": SOURCE_STATE_ID, "bundle_id": BUNDLE_ID, "integrity_verified": True}
        input_set = build_scenario_input_set(SOURCE_STATE_ID)
        input_set["geographic_confidence"] = "UNRESOLVED"
        self.assertIn("GEOGRAPHY_INVALID", evaluate_eligibility(state, input_set)["reasons"])

    def test_missing_assumption_traceability_fails_closed(self):
        state = {"source_state_id": SOURCE_STATE_ID, "bundle_id": BUNDLE_ID, "integrity_verified": True}
        input_set = build_scenario_input_set(SOURCE_STATE_ID)
        input_set["assumptions"] = ()
        self.assertIn("ASSUMPTION_TRACEABILITY_INVALID", evaluate_eligibility(state, input_set)["reasons"])

    def test_wp01_execution_tables_are_not_touched(self):
        ingest_water_resilience_bundle(self.store, ROOT)
        self.assertEqual(self.store.connection.execute("SELECT COUNT(*) FROM execution_attempts").fetchone()[0], 0)
        self.assertEqual(self.store.connection.execute("SELECT COUNT(*) FROM candidate_signals").fetchone()[0], 0)

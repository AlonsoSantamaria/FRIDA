from __future__ import annotations

from datetime import UTC, datetime
import unittest

from frida.persistence import StagingStore
from frida.taipei_observation import TaipeiObservationFabricProvider
from frida.taipei_observation import (
    TAIPEI_DRAINAGE,
    TAIPEI_RAIN,
    TAIPEI_WORKS,
    classify_state,
    normalize_drainage,
    normalize_rainfall,
    normalize_works,
)


NOW = datetime(2026, 8, 29, 13, 44, tzinfo=UTC)


class TaipeiObservationTests(unittest.TestCase):
    def test_works_drops_named_contacts_but_keeps_operational_location(self):
        result = normalize_works({"features": [{"geometry": {"type": "Point", "coordinates": [1, 2]}, "properties": {
            "Ac_no": "W-1", "AppTime": "115/08/29 21:40:00", "Addr": "Road", "NPurp": "Drainage", "WItem": "Excavation", "Cb_Da": "115/08/29", "Ce_Da": "115/09/01", "IsBlock": "否", "IsStay": "是", "DLen": "12", "App_Name": "Applicant", "C_Name": "Company", "Tc_Na": "Person", "Tc_Ma": "Person", "Tc_Tl": "Phone", "Tc_Ma3": "Person", "Tc_Tl3": "Phone",
        }}]}, retrieved_at=NOW)
        item = result.canonical_state["active_works"][0]
        self.assertEqual(result.source_id, TAIPEI_WORKS)
        self.assertEqual(item["work_id"], "W-1")
        self.assertNotIn("Person", str(result.canonical_state))
        self.assertNotIn("Applicant", str(result.canonical_state))
        self.assertEqual(len(result.fingerprint_sha256), 64)

    def test_publication_or_retrieval_time_does_not_change_station_state(self):
        payload = {"data": [{"stationNo": "001", "stationName": "Station", "recTime": "202608292140", "rain": 1.5}]}
        one = normalize_rainfall(payload, retrieved_at=NOW)
        two = normalize_rainfall(payload, retrieved_at=datetime(2026, 8, 29, 13, 45, tzinfo=UTC))
        self.assertEqual(one.source_id, TAIPEI_RAIN)
        self.assertEqual(one.fingerprint_sha256, two.fingerprint_sha256)
        self.assertEqual(classify_state(one.fingerprint_sha256, two), "SAME_STATE")

    def test_drainage_preserves_only_operational_station_state(self):
        result = normalize_drainage({"data": [{"stationNo": "U1", "stationName": "Drain", "recTime": "202608292144", "levelOut": 15.56, "voltage": 12.93, "groundFar": 3.75}]}, retrieved_at=NOW)
        self.assertEqual(result.source_id, TAIPEI_DRAINAGE)
        self.assertEqual(result.canonical_state["stations"], [{"station_id": "U1", "station_name": "Drain", "observed_value": 15.56}])
        self.assertEqual(classify_state(None, result), "ORDINARY_CHANGE")

    def test_append_only_observation_keeps_provenance_separate_from_state(self):
        store = StagingStore(":memory:")
        snapshot = normalize_rainfall({"data": [{"stationNo": "001", "stationName": "Station", "recTime": "202608292140", "rain": 0}]}, retrieved_at=NOW).persisted()
        first = store.append_source_fabric_observation(snapshot, "ORDINARY_CHANGE")
        second = store.append_source_fabric_observation(snapshot, "SAME_STATE")
        self.assertNotEqual(first, second)
        latest = store.latest_source_fabric_observation(TAIPEI_RAIN)
        self.assertEqual(latest["classification"], "SAME_STATE")
        self.assertNotIn("canonical_state", latest["provenance_json"])
        self.assertIn("stations", latest["canonical_state_json"])
        store.close()

    def test_provider_exposes_all_three_independent_sources_from_injected_public_payloads(self):
        values = {
            "Todaywork": {"features": []},
            "Rain": {"data": []},
            "Sewer": {"data": []},
        }
        def fetch(url):
            return next(value for marker, value in values.items() if marker in url)
        snapshots = TaipeiObservationFabricProvider(fetch).snapshots()
        self.assertEqual({item.source_id for item in snapshots}, {TAIPEI_WORKS, TAIPEI_RAIN, TAIPEI_DRAINAGE})


if __name__ == "__main__":
    unittest.main()

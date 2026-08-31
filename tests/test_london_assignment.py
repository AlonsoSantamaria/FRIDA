from __future__ import annotations

from datetime import UTC, datetime
import tempfile
import unittest
from pathlib import Path

from frida.london_observation import (
    EA_STATION_URL, EA_THAMES_TIDEWAY, PLANNING_SEARCH_URL, PLANNING_SW8,
    TFL_VICTORIA, TFL_URL, LONDON_SAFETY_MPS, LondonObservationFabricProvider, normalize_environment,
    normalize_planning, normalize_tfl,
)
from frida.persistence import StagingStore
from frida.staging import StagingService
from frida.london_time_travel import LondonTimeTravel, SEQUENCE


class LondonAssignmentTests(unittest.TestCase):
    def test_normalizers_keep_provenance_time_out_of_operational_fingerprint(self):
        tfl = [{"id": "victoria", "name": "Victoria", "modified": "2026-08-27T12:26:42Z", "lineStatuses": [{"statusSeverity": 10, "statusSeverityDescription": "Good Service"}]}]
        one = normalize_tfl(tfl, retrieved_at=datetime(2026, 8, 29, tzinfo=UTC))
        two = normalize_tfl(tfl, retrieved_at=datetime(2026, 8, 30, tzinfo=UTC))
        self.assertEqual(one.fingerprint_sha256, two.fingerprint_sha256)
        self.assertEqual(one.source_timestamp, "2026-08-27T12:26:42Z")
        planning = normalize_planning({"hits": {"hits": [{"_id": "Wandsworth-2017_7069", "_source": {"id": "Wandsworth-2017_7069", "applicationStatus": "Completed", "decisionDate": "2018-10-25", "actualCompletionDate": "2021-12-01"}}]}})
        self.assertEqual(planning.source_id, PLANNING_SW8)
        self.assertEqual(planning.canonical_state["records"][0]["application_id"], "Wandsworth-2017_7069")
        env = normalize_environment({}, {"items": [{"value": -1.393, "dateTime": "2026-08-29T23:15:00Z"}]})
        self.assertEqual(env.source_id, EA_THAMES_TIDEWAY)
        self.assertEqual(env.canonical_state["value"], -1.393)

    def test_provider_uses_three_official_boundaries_without_exposing_key(self):
        calls=[]
        def fetch(url, **kwargs):
            calls.append((url, kwargs))
            if url.startswith(TFL_URL):
                return [{"id":"victoria","lineStatuses":[{"statusSeverityDescription":"Good Service"}]}]
            if url == PLANNING_SEARCH_URL:
                return {"hits":{"hits":[]}}
            if url == EA_STATION_URL:
                return {"items":[]}
            return {"items":[{"value":0.1,"dateTime":"2026-08-29T23:15:00Z"}]}
        import os
        old=os.environ.get("FRIDA_TFL_APP_KEY"); os.environ["FRIDA_TFL_APP_KEY"]="test-key"
        try:
            snapshots=LondonObservationFabricProvider(
                fetch, due_source_ids=lambda: (TFL_VICTORIA, PLANNING_SW8, EA_THAMES_TIDEWAY)
            ).snapshots()
        finally:
            if old is None: os.environ.pop("FRIDA_TFL_APP_KEY",None)
            else: os.environ["FRIDA_TFL_APP_KEY"]=old
        self.assertEqual({item.source_id for item in snapshots},{TFL_VICTORIA,PLANNING_SW8,EA_THAMES_TIDEWAY})
        self.assertNotIn("test-key", repr([item.persisted() for item in snapshots]))
        self.assertEqual(len(calls), 4)

    def test_tfl_status_can_use_bounded_public_read_without_copying_cloud_secret(self):
        import os
        old = os.environ.pop("FRIDA_TFL_APP_KEY", None)
        try:
            snapshot = LondonObservationFabricProvider(
                lambda url, **_kwargs: [{"id": "victoria", "lineStatuses": [{"statusSeverityDescription": "Good Service"}]}],
                due_source_ids=lambda: (TFL_VICTORIA,),
            ).snapshots()
        finally:
            if old is not None: os.environ["FRIDA_TFL_APP_KEY"] = old
        self.assertEqual(snapshot[0].source_id, TFL_VICTORIA)

    def test_archives_are_verified_and_london_is_fresh_active_assignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            service=StagingService(str(Path(tmp)/"frida.sqlite3"), source_provider=lambda: ())
            try:
                self.assertIsNone(service.store.active_assignment())
                result=service.activate_london_assignment()
                self.assertEqual(result["assignment"]["assignment_id"], "LONDON_FINAL_ACTIVE")
                self.assertTrue(all(service.store.verify_assignment_archive(str(item["archive_id"])) for item in result["archives"]))
                self.assertEqual(service.store.recent_observation_cycles(), [])
                self.assertEqual(set(service.store.due_observation_sources("LONDON_FINAL_ACTIVE", datetime.now(tz=UTC))), {TFL_VICTORIA,PLANNING_SW8,EA_THAMES_TIDEWAY,"LONDON_GLA_HOUSING_LED_SW8",LONDON_SAFETY_MPS})
                self.assertEqual(service.observation_status()["state"], "STOPPED")
            finally:
                service.close()

    def test_time_travel_preserves_real_chronology_without_semantic_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=StagingStore(Path(tmp)/"frida.sqlite3")
            try:
                store.activate_london_assignment()
                replay_id=LondonTimeTravel(store).start("TEST", step_seconds=.001)
                import time
                for _ in range(100):
                    replay=store.accelerated_replay(replay_id)
                    if replay and replay["status"] != "RUNNING": break
                    time.sleep(.01)
                self.assertEqual(replay["status"], "COMPLETED")
                self.assertEqual([row["source_date"] for row in replay["snapshots"]], [item.source_date.isoformat() for item in SEQUENCE])
                self.assertTrue(all(row["state"] == "OBSERVED_NO_STRATEGIC_DISPATCH" for row in replay["snapshots"]))
                self.assertTrue(all(event["payload"].get("semantic_calls", 0) == 0 for event in replay["events"]))
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()

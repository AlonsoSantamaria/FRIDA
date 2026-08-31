from datetime import UTC, datetime
import unittest

from frida.metrobus_gtfs_rt import MetrobusCredentialPending, MetrobusGtfsRtAdapter, classify_operational_change, normalise_gtfs_realtime


def fixture(*, header_timestamp: int = 1_788_000_000, alert: str = ""):
    entities = [
        {"id": "private-vehicle-a", "vehicle": {"trip": {"route_id": "L1", "direction_id": 1}, "current_status": "IN_TRANSIT_TO", "stop_id": "MB001", "timestamp": header_timestamp}},
        {"id": "private-trip-a", "trip_update": {"trip": {"route_id": "L1", "direction_id": 1}, "stop_time_update": [{"stop_id": "MB002", "schedule_relationship": "SCHEDULED"}]}},
    ]
    if alert:
        entities.append({"id": "private-alert-a", "alert": {"effect": alert, "cause": "UNKNOWN_CAUSE", "informed_entity": [{"route_id": "L1", "stop_id": "MB002"}]}})
    return {"header": {"gtfs_realtime_version": "2.0", "timestamp": header_timestamp}, "entity": entities}


class MetrobusGtfsRtTests(unittest.TestCase):
    def test_identity_keeps_retrieval_and_header_time_out_of_operational_fingerprint(self):
        at = datetime(2026, 8, 28, tzinfo=UTC)
        first_identity, first = normalise_gtfs_realtime(fixture(), retrieved_at=at)
        second_identity, second = normalise_gtfs_realtime(fixture(header_timestamp=1_788_003_600), retrieved_at=datetime(2026, 8, 29, tzinfo=UTC))
        self.assertNotEqual(first_identity.retrieved_at, second_identity.retrieved_at)
        self.assertNotEqual(first_identity.feed_header_timestamp, second_identity.feed_header_timestamp)
        self.assertEqual(first.fingerprint_sha256, second.fingerprint_sha256)
        self.assertNotIn("private-vehicle-a", str(first.facts))
        self.assertEqual(classify_operational_change(first, second), "SAME_STATE")

    def test_fixture_policy_can_classify_alert_change_without_freezing_production_thresholds(self):
        _, before = normalise_gtfs_realtime(fixture())
        _, after = normalise_gtfs_realtime(fixture(alert="DETOUR"))
        class FixturePolicy:
            def classify(self, previous, current):
                return "POTENTIALLY_ELIGIBLE_CHANGE" if current.facts["alerts"] else "ORDINARY_CHANGE"
        self.assertEqual(classify_operational_change(before, after, FixturePolicy()), "POTENTIALLY_ELIGIBLE_CHANGE")

    def test_adapter_fails_closed_while_official_credential_is_pending(self):
        with self.assertRaises(MetrobusCredentialPending):
            MetrobusGtfsRtAdapter().snapshots()

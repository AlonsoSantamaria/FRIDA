from datetime import UTC, datetime
import unittest

from frida.smn_probe import classify_source_state, normalise_queretaro


def record(day: int, maximum: str = "28.1") -> dict[str, str]:
    return {"ides": "22", "idmun": "14", "nmun": "Querétaro", "nes": "Querétaro de Arteaga", "dloc": f"202608{28 + day:02}T00", "ndia": str(day), "tmax": maximum, "tmin": "12.0", "desciel": "Cielo nublado", "probprec": "0", "prec": "0.0", "velvien": "13.7", "dirvienc": "Este", "dirvieng": "90.0", "raf": "34.9", "cc": "32.2"}


class SMNProbeTests(unittest.TestCase):
    def test_normalisation_selects_only_queretaro_and_is_stable(self):
        other = {**record(0), "ides": "09", "idmun": "15", "nmun": "Other"}
        at = datetime(2026, 8, 28, tzinfo=UTC)
        snapshot = normalise_queretaro([record(1), other, record(0)], retrieved_at=at)
        self.assertEqual(snapshot["state_id"], "22")
        self.assertEqual(snapshot["municipality_id"], "14")
        self.assertEqual([row["ndia"] for row in snapshot["forecast"]], ["0", "1"])
        self.assertEqual(snapshot["retrieved_at"], at.isoformat())
        self.assertEqual(len(snapshot["content_fingerprint_sha256"]), 64)

    def test_identical_and_changed_normalised_states_are_classified_deterministically(self):
        first = normalise_queretaro([record(0)], retrieved_at=datetime(2026, 8, 28, tzinfo=UTC))
        same = normalise_queretaro([record(0)], retrieved_at=datetime(2026, 8, 29, tzinfo=UTC))
        changed = normalise_queretaro([record(0, "29.1")])
        self.assertEqual(classify_source_state(first, same), "SAME_SOURCE_STATE")
        self.assertEqual(classify_source_state(first, changed), "SOURCE_STATE_CHANGED")

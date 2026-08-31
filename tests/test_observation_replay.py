from datetime import datetime, UTC
import unittest
from frida.domain import EvidenceClass
from frida.observation import HistoricalReplay, ReplaySnapshot, SharedObserver
T=datetime(2026,8,23,tzinfo=UTC)
def snap(source, hash, seq): return ReplaySnapshot(source,"official://"+source,datetime(2025,5,22,tzinfo=UTC),hash,EvidenceClass.REAL,seq,T)
class ObserverReplayTests(unittest.TestCase):
 def test_same_shared_contract_supports_two_sources(self):
  self.assertEqual(SharedObserver("DENUE").observe(snap("DENUE","a",1)).source_id,"DENUE")
  self.assertEqual(SharedObserver("SEMAFORO").observe(snap("SEMAFORO","b",1)).source_id,"SEMAFORO")
 def test_duplicate_snapshot_is_idempotent(self):
  o=SharedObserver("DENUE"); x=snap("DENUE","a",1); self.assertIsNotNone(o.observe(x)); self.assertIsNone(o.observe(x))
 def test_replay_preserves_source_time_separately_from_observation_time(self):
  x=snap("DENUE","a",1); signal=HistoricalReplay([x]).run(SharedObserver("DENUE"))[0]; self.assertNotEqual(x.source_date,signal.observed_date)
 def test_duplicate_replay_sequence_fails(self):
  with self.assertRaises(ValueError): HistoricalReplay([snap("DENUE","a",1),snap("DENUE","b",1)])

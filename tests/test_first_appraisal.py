from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from frida.first_appraisal import FirstAppraisalBlocked, FirstAppraisalService, compact_bundle
from frida.bounded_research import BoundedLondonResearch
from frida.london_observation import LondonSnapshot, PLANNING_SW8, TFL_VICTORIA
from frida.persistence import StagingStore
from frida.semantic_completion import SemanticCompletionValidationError, parse_native_first_appraisal
from frida.semantic_completion import parse_native_enriched_appraisal


class FakeStages:
    def __init__(self, response): self.response, self.closed = response, False
    def first_appraisal(self, bundle, allowed):
        return self.response, {"model": "test", "usage": {"total_token_count": 9}, "latency_ms": 1, "configured_max_output_tokens": 4096}
    def close(self): self.closed = True


class FakeResearchStages:
    def __init__(self): self.bundle = None
    def enriched_appraisal(self, bundle, allowed):
        self.bundle = bundle
        return {
            "strategic_interest": "POSSIBLE", "opportunity_family": "OPPORTUNITY",
            "hypothesis_direction": "STRENGTHENED", "watch_interpretation": "BETTER_JUSTIFIED",
            "strategic_question": "Does the combined context merit a Watch?",
            "how_evidence_changes_hypothesis": "The two bounded sources provide relevant context.",
            "evidence_ids_used": sorted(allowed), "missing_evidence": ["Capacity assessment"],
            "allowed_context_requests": [], "uncertainties": ["No demand measurement."],
            "further_research_has_positive_information_value": False,
        }, {"model": "test", "usage": {"total_token_count": 12}, "latency_ms": 1}
    def close(self): pass


class FakeResearchProvider:
    def snapshots(self):
        now = datetime(2026, 8, 30, tzinfo=UTC)
        return (
            LondonSnapshot(PLANNING_SW8, "Official planning", "https://official.example/planning", now, "2026-08-30T00:00:00Z", {"coverage": "SW8"}, {"postcode": "SW8", "records": []}, "a" * 64),
            LondonSnapshot(TFL_VICTORIA, "Transport for London", "https://official.example/tfl", now, "2026-08-30T00:00:00Z", {"coverage": "Victoria"}, {"line_id": "victoria", "status": "Good Service"}, "b" * 64),
        )


def observation(store: StagingStore) -> dict[str, object]:
    store.activate_london_assignment()
    snapshot = {
        "source_id": "LONDON_PLANNING_SW8", "authority": "Official planning", "source_url": "https://official.example/planning",
        "retrieved_at": datetime(2026, 8, 30, tzinfo=UTC).isoformat(), "source_timestamp": "2026-08-30T00:00:00Z",
        "geography": {"coverage": "SW8", "kind": "development"}, "fingerprint_sha256": "a" * 64,
        "adapter_version": "test", "normalization_version": "test", "canonical_state": {"records": [{"status": "Completed"}]},
    }
    store.append_source_fabric_observation(snapshot, "ORDINARY_CHANGE", "LONDON_FINAL_ACTIVE")
    return store.latest_source_fabric_observation("LONDON_PLANNING_SW8", "LONDON_FINAL_ACTIVE")


class FirstAppraisalTests(unittest.TestCase):
    def test_contract_rejects_external_evidence_and_unsupported_research(self):
        valid = {"strategic_interest": "POSSIBLE", "opportunity_family": "OPPORTUNITY", "strategic_question": "What changed?", "why_it_might_matter": "A planning transition may affect place use.", "evidence_ids_used": ["e1"], "missing_evidence": ["scale"], "allowed_context_requests": ["LONDON_TFL_VICTORIA"], "uncertainties": ["No scale."], "research_warranted": True}
        self.assertEqual(parse_native_first_appraisal(valid, {"e1"})["strategic_interest"], "POSSIBLE")
        valid["evidence_ids_used"] = ["external"]
        with self.assertRaises(SemanticCompletionValidationError): parse_native_first_appraisal(valid, {"e1"})

    def test_appraisal_is_append_only_deduplicated_and_non_authorizing(self):
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3")
            row = observation(store)
            response = {"strategic_interest": "POSSIBLE", "opportunity_family": "OPPORTUNITY", "strategic_question": "Does this planning change have area impact?", "why_it_might_matter": "It may warrant bounded context.", "evidence_ids_used": [str(row["source_observation_id"])], "missing_evidence": ["scale"], "allowed_context_requests": ["LONDON_TFL_VICTORIA"], "uncertainties": ["No corroboration."], "research_warranted": True}
            stages = FakeStages(response)
            service = FirstAppraisalService(store, stages)
            result, meta = service.appraise("LONDON_FINAL_ACTIVE", [row])
            self.assertEqual(result["authorization"], "NON_AUTHORIZING_FIRST_APPRAISAL")
            self.assertEqual(result["research_dispatch"], "HELD")
            self.assertEqual(meta["usage"]["total_token_count"], 9)
            self.assertEqual(store.status()["candidate_signals"], 0)
            with self.assertRaises(FirstAppraisalBlocked): service.appraise("LONDON_FINAL_ACTIVE", [row])
            service.close(); self.assertTrue(stages.closed)
            store.close()

    def test_bundle_contains_only_normalized_facts_and_assignment_boundary(self):
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3")
            row = observation(store)
            bundle = compact_bundle("LONDON_FINAL_ACTIVE", [row])
            self.assertEqual(bundle["assignment_id"], "LONDON_FINAL_ACTIVE")
            self.assertEqual(bundle["evidence"][0]["source_id"], "LONDON_PLANNING_SW8")
            self.assertNotIn("source_url", bundle["evidence"][0])
            store.close()

    def test_enriched_contract_cannot_convert_non_interest_into_watch(self):
        value = {"strategic_interest": "NONE", "opportunity_family": "UNKNOWN", "hypothesis_direction": "WEAKENED", "watch_interpretation": "BETTER_JUSTIFIED", "strategic_question": "Question", "how_evidence_changes_hypothesis": "Evidence", "evidence_ids_used": ["e1"], "missing_evidence": [], "allowed_context_requests": [], "uncertainties": ["Uncertain"], "further_research_has_positive_information_value": False}
        with self.assertRaises(SemanticCompletionValidationError): parse_native_enriched_appraisal(value, {"e1"})

    def test_bounded_research_uses_exactly_the_two_authorized_contexts_without_case_authority(self):
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3")
            store.activate_london_assignment()
            stages = FakeResearchStages()
            result, meta, evidence = BoundedLondonResearch(store, FakeResearchProvider(), stages).run_once("LONDON_FINAL_ACTIVE")
            self.assertEqual({item["source_id"] for item in evidence}, {PLANNING_SW8, TFL_VICTORIA})
            self.assertEqual({item["source_id"] for item in stages.bundle["evidence"]}, {PLANNING_SW8, TFL_VICTORIA})
            self.assertEqual(result["watch_interpretation"], "BETTER_JUSTIFIED")
            self.assertEqual(meta["usage"]["total_token_count"], 12)
            self.assertEqual(store.status()["candidate_signals"], 0)
            self.assertEqual(store.status().get("cases", 0), 0)
            self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM bounded_research_appraisals WHERE status='VALIDATED'").fetchone()[0], 1)
            store.close()

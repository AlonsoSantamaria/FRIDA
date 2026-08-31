from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from frida.persistence import StagingStore
from frida.source_registry import SourceProposal, SourceRegistry
from frida.source_discovery import SourceDiscoveryService
from frida.news_clues import UrbanNewsClue, normalize_clue


class SourceRegistryTests(unittest.TestCase):
    def test_pre_authorized_official_source_is_remembered_once_and_approved(self):
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3"); store.activate_london_assignment()
            proposal = SourceProposal("London planning notices", "Greater London Authority", "https://planningdata.london.gov.uk/", "London", "OFFICIAL_GOVERNMENT", ("planning",), "Planning gap", "Development scale", "Public official service", "Daily", "Structured extraction", "NO_PERSONAL_DATA", "OFFICIAL")
            registry = SourceRegistry(store)
            first = registry.remember("LONDON_FINAL_ACTIVE", proposal, operationally_validated=True)
            second = registry.remember("LONDON_FINAL_ACTIVE", proposal)
            self.assertEqual(first["status"], "APPROVED")
            self.assertEqual(second["outcome"], "ALREADY_REMEMBERED")
            self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM source_registry_events").fetchone()[0], 3)
            store.close()

    def test_privacy_exception_is_suspended_not_operational(self):
        with TemporaryDirectory() as directory:
            store = StagingStore(Path(directory) / "frida.sqlite3"); store.activate_london_assignment()
            proposal = SourceProposal("Unsafe", "Publisher", "https://example.org/x", "London", "RECOGNIZED_NEWS", ("safety",), "Gap", "Context", "Public", "Daily", "Normalise", "PERSON_LEVEL", "RECOGNIZED")
            self.assertEqual(SourceRegistry(store).remember("LONDON_FINAL_ACTIVE", proposal)["status"], "SUSPENDED")
            store.close()

    def test_discovery_is_london_scoped_deduplicated_and_bounded(self):
        with TemporaryDirectory() as directory:
            store=StagingStore(Path(directory) / "frida.sqlite3"); store.activate_london_assignment()
            service=SourceDiscoveryService(store)
            results=service.discover("LONDON_FINAL_ACTIVE", "planning and flood resilience")
            self.assertLessEqual(len(results), 3)
            self.assertTrue(all(item["status"] == "SCREENED" for item in results))
            repeated=service.discover("LONDON_FINAL_ACTIVE", "planning and flood resilience")
            self.assertTrue(all(item["outcome"] == "ALREADY_REMEMBERED" for item in repeated))
            store.close()

    def test_targeted_news_is_a_clue_never_a_conclusion(self):
        clue = normalize_clue(UrbanNewsClue(
            "Greater London Authority", "https://www.london.gov.uk/press-releases",
            "OFFICIAL_ANNOUNCEMENT", ("planning", "celebrity"), "2026-08-30", "Urban planning update",
        ))
        self.assertEqual(clue["topics"], ["planning"])
        self.assertEqual(clue["role"], "CLUE_ONLY_REQUIRES_INDEPENDENT_GOVERNED_CORROBORATION")
        self.assertFalse(clue["may_conclude"])
        self.assertFalse(clue["may_create_signal"])

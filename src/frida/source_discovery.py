"""Bounded London source discovery: proposal first, policy before observation."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from .source_registry import SourceProposal, SourceRegistry

DAILY_DISCOVERY_CAP = 5
PER_QUESTION_SEARCH_CAP = 3

# Authoritative, public London candidates. The selector may choose none; this is
# a discovery catalogue, not evidence and not an operational source list.
LONDON_DISCOVERY_CATALOGUE = (
    {"source_name": "GLA 2024 housing-led population projections", "publisher": "Greater London Authority Demography", "canonical_url": "https://data.london.gov.uk/download/2zp76/q43/gla_2024_housing_led_central_msoa_la_level.xlsx", "geographic_scope": "Lambeth and Wandsworth borough context for SW8", "source_class": "OPEN_DATA", "strategic_domains": ("housing", "population", "occupancy", "infrastructure"), "access_licensing_notes": "Official GLA public data release; projection context, not observed demand.", "freshness_cadence": "Annual release", "normalization_method": "Aggregate borough person totals by year; publication date excluded from state fingerprint", "privacy_assessment": "AGGREGATE_ONLY", "reliability_assessment": "OFFICIAL"},
    {"source_name": "Environment Agency Flood Monitoring", "publisher": "Environment Agency", "canonical_url": "https://environment.data.gov.uk/flood-monitoring/", "geographic_scope": "England / London", "source_class": "STATUTORY_AGENCY", "strategic_domains": ("flood", "resilience", "drainage"), "access_licensing_notes": "Public government data service.", "freshness_cadence": "Near real-time where published", "normalization_method": "Station/measure state with timestamp excluded from operational fingerprint", "privacy_assessment": "NO_PERSONAL_DATA", "reliability_assessment": "OFFICIAL"},
    {"source_name": "London Planning Datahub", "publisher": "Greater London Authority", "canonical_url": "https://planningdata.london.gov.uk/", "geographic_scope": "Greater London", "source_class": "OFFICIAL_GOVERNMENT", "strategic_domains": ("planning", "development", "land-use"), "access_licensing_notes": "Official public planning service.", "freshness_cadence": "Source-published", "normalization_method": "Application lifecycle state", "privacy_assessment": "NO_PERSONAL_DATA", "reliability_assessment": "OFFICIAL"},
    {"source_name": "MPS Recorded Crime: Geographic Breakdown", "publisher": "Metropolitan Police Service via London Datastore", "canonical_url": "https://data.london.gov.uk/download/exy3m/e4x/MPS%20Borough%20Level%20Crime%20(most%20recent%2024%20months).csv", "geographic_scope": "Lambeth and Wandsworth borough context for SW8", "source_class": "OPEN_DATA", "strategic_domains": ("urban-safety", "public-realm", "accessibility"), "access_licensing_notes": "Official MPS aggregate borough publication; no person-level use.", "freshness_cadence": "Monthly", "normalization_method": "Three-month aggregate borough crime-category context; publication/retrieval timestamp excluded from state fingerprint", "privacy_assessment": "AGGREGATE_ONLY", "reliability_assessment": "OFFICIAL"},
    {"source_name": "London City Hall official announcements", "publisher": "Greater London Authority", "canonical_url": "https://www.london.gov.uk/press-releases", "geographic_scope": "Greater London", "source_class": "OFFICIAL_ANNOUNCEMENT", "strategic_domains": ("planning", "housing", "transport", "infrastructure", "resilience", "investment", "public-realm"), "access_licensing_notes": "Official announcement clue source; independent governed corroboration required before any conclusion.", "freshness_cadence": "Publisher-led", "normalization_method": "Targeted urban-clue metadata only; never evidence of a conclusion", "privacy_assessment": "PUBLIC_INSTITUTIONAL", "reliability_assessment": "OFFICIAL"},
)


class SourceDiscoveryBlocked(RuntimeError): pass


class SourceDiscoveryService:
    def __init__(self, store: Any, selector: Callable[[str, tuple[dict[str, Any], ...]], list[dict[str, Any]]] | None = None):
        self.store, self.selector = store, selector or self._policy_selector

    @staticmethod
    def _policy_selector(question: str, candidates: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
        words=set(question.lower().replace("/", " ").split())
        return [item for item in candidates if words.intersection({domain.lower() for domain in item["strategic_domains"]})][:PER_QUESTION_SEARCH_CAP]

    def discover(self, assignment_id: str, strategic_question: str) -> list[dict[str, str]]:
        if assignment_id != "LONDON_FINAL_ACTIVE": raise SourceDiscoveryBlocked("active assignment boundary")
        if self.store.source_discovery_count_since(assignment_id, datetime.now(tz=UTC)-timedelta(days=1)) >= DAILY_DISCOVERY_CAP:
            raise SourceDiscoveryBlocked("daily discovery cap reached")
        selected=self.selector(strategic_question, LONDON_DISCOVERY_CATALOGUE)[:PER_QUESTION_SEARCH_CAP]
        registry=SourceRegistry(self.store); results=[]
        for item in selected:
            proposal=SourceProposal(**item, why_proposed=f"May reduce uncertainty in: {strategic_question}", evidence_gap="Declared strategic uncertainty")
            results.append(registry.remember(assignment_id, proposal))
        return results

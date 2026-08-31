"""Versioned, reversible active-city configuration for FRIDA observation."""
from __future__ import annotations

from dataclasses import dataclass


LONDON_ASSIGNMENT_ID = "LONDON_FINAL_ACTIVE"
TAIPEI_ARCHIVE_ASSIGNMENT_ID = "TAIPEI_TECHNICAL_ARCHIVE"
QUERETARO_ARCHIVE_ASSIGNMENT_ID = "QUERETARO_HISTORICAL_ARCHIVE"


@dataclass(frozen=True, slots=True)
class CityAssignmentDefinition:
    assignment_id: str
    city_name: str
    country_name: str
    identity_label: str
    observing_label: str
    source_ids: tuple[str, ...]


LONDON = CityAssignmentDefinition(
    assignment_id=LONDON_ASSIGNMENT_ID,
    city_name="London",
    country_name="United Kingdom",
    identity_label="LONDON, UNITED KINGDOM",
    observing_label="FRIDA is observing London",
    source_ids=("LONDON_TFL_VICTORIA", "LONDON_PLANNING_SW8", "LONDON_EA_THAMES_TIDEWAY", "LONDON_GLA_HOUSING_LED_SW8", "LONDON_MPS_BOROUGH_SAFETY_SW8"),
)


def public_identity(assignment: dict[str, object] | None) -> dict[str, str]:
    if not assignment:
        return {"city": "FRIDA", "country": "", "label": "FRIDA", "observing": "FRIDA is observing", "identity_asset_url": ""}
    city = str(assignment.get("city_name", "FRIDA"))
    country = str(assignment.get("country_name", ""))
    identity_asset_url = "/assets/london-city-coat-of-arms.svg" if str(assignment.get("assignment_id", "")) == LONDON_ASSIGNMENT_ID else ""
    return {
        "city": city,
        "country": country,
        "label": f"{city.upper()}, {country.upper()}".strip(", "),
        "observing": f"FRIDA is observing {city}",
        "identity_asset_url": identity_asset_url,
    }

"""Aggregate, place-based London safety context.

This adapter intentionally consumes only the Metropolitan Police Service's
borough-level monthly publication.  It does not retain person, incident,
victim, suspect, address, or street-level information and it is not a
prediction or a policing decision input.
"""
from __future__ import annotations

import csv
from datetime import UTC, datetime
from hashlib import sha256
import io
import json
from urllib.request import Request, urlopen

from .london_observation import LondonSnapshot

LONDON_SAFETY_MPS = "LONDON_MPS_BOROUGH_SAFETY_SW8"
URL = "https://data.london.gov.uk/download/exy3m/e4x/MPS%20Borough%20Level%20Crime%20(most%20recent%2024%20months).csv"
BOROUGHS = ("Lambeth", "Wandsworth")


def normalize_mps_borough_csv(payload: bytes, *, retrieved_at: datetime | None = None) -> LondonSnapshot:
    rows = list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    if not rows or not rows[0].get("BOCU"):
        raise ValueError("MPS borough publication has no usable rows")
    months = tuple(key for key in rows[0] if len(key) == 6 and key.isdigit())
    if len(months) < 3:
        raise ValueError("MPS borough publication has insufficient monthly columns")
    period = months[-3:]
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        if row.get("BOCU") not in BOROUGHS:
            continue
        group = str(row.get("Group") or "UNKNOWN")
        value = sum(int(row.get(month) or 0) for month in period)
        grouped.setdefault(group, {borough: 0 for borough in BOROUGHS})
        grouped[group][str(row["BOCU"])] += value
    if not grouped:
        raise ValueError("MPS borough publication has no Lambeth/Wandsworth aggregate context")
    state = {
        "kind": "aggregate_place_based_safety_context",
        "scope": "Lambeth and Wandsworth borough context for SW8/Battersea",
        "period_months": list(period),
        "groups": [
            {"group": group, "borough_totals": grouped[group], "combined_total": sum(grouped[group].values())}
            for group in sorted(grouped)
        ],
        "limitations": [
            "Recorded crime is an aggregate contextual indicator, not a measure of individual behaviour or causality.",
            "Borough geography is broader than SW8 and must not be used for predictive policing.",
        ],
    }
    canonical = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return LondonSnapshot(
        LONDON_SAFETY_MPS,
        "Metropolitan Police Service via London Datastore",
        URL,
        retrieved_at or datetime.now(tz=UTC),
        period[-1],
        {"coverage": "Lambeth and Wandsworth boroughs; aggregate context only", "kind": "urban safety dynamics"},
        state,
        sha256(canonical.encode()).hexdigest(),
        "london-mps-borough-safety-v1",
        "london-mps-borough-safety-normalization-v1",
    )


def fetch_mps_borough_safety() -> LondonSnapshot:
    request = Request(URL, headers={"Accept": "text/csv", "User-Agent": "FRIDA/1.0 official-observation"})
    with urlopen(request, timeout=60) as response:  # nosec B310: fixed official HTTPS source
        return normalize_mps_borough_csv(response.read())

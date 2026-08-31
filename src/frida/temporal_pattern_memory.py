"""Deterministic evidence assessment over persisted source observations.

It is deliberately not a Signal or eligibility engine and never calls a model.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from collections import Counter
from typing import Iterable, Mapping


@dataclass(frozen=True)
class PatternAssessment:
    state: str
    source_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]
    rule_version: str = "temporal-pattern-memory-v1"


def _geography(row: Mapping[str, object]) -> str:
    """Read retained provenance without making geography part of the signal path."""
    if row.get("geography"):
        return str(row["geography"])
    raw = row.get("provenance_json")
    if isinstance(raw, str):
        try:
            value = json.loads(raw).get("geography", "")
            return str(value)
        except (TypeError, ValueError):
            return ""
    return ""


def assess(observations: Iterable[Mapping[str, object]]) -> PatternAssessment:
    rows = tuple(observations)
    changed = tuple(row for row in rows if row.get("classification") == "ORDINARY_CHANGE")
    ids = tuple(str(row.get("source_observation_id", "")) for row in rows)
    sources = tuple(sorted({str(row.get("source_id", "")) for row in rows if row.get("source_id")}))
    changed_sources = {str(row.get("source_id", "")) for row in changed if row.get("source_id")}
    changed_geographies = {_geography(row) for row in changed}
    # A cross-source pattern requires a compatible declared geography.  It is
    # an auditable memory classification only: it never creates a Signal.
    per_source = Counter(str(row.get("source_id", "")) for row in changed if row.get("source_id"))
    max_repetitions = max(per_source.values(), default=0)
    if len(changed_sources) >= 2 and len(changed_geographies) == 1 and "" not in changed_geographies:
        state = "CROSS_SOURCE_PATTERN"
    elif max_repetitions >= 3:
        state = "PERSISTENT"
    elif max_repetitions >= 2:
        state = "REPEATED"
    else:
        state = "NO_PATTERN"
    return PatternAssessment(state, sources, ids)

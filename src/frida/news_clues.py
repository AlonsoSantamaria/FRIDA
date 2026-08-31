"""Governed clue handling for targeted urban news and official announcements.

Clues can warrant a look.  They cannot establish a FRIDA conclusion, signal,
candidate, case, causal relationship, or governance outcome.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

PRIORITY_TOPICS = frozenset({
    "planning", "housing", "redevelopment", "construction", "infrastructure", "transport",
    "water", "flood", "resilience", "investment", "employment", "environment", "land-use",
    "public-realm", "urban-safety",
})
RECOGNIZED_CLASSES = frozenset({"OFFICIAL_ANNOUNCEMENT", "RECOGNIZED_NEWS", "INSTITUTIONAL"})


@dataclass(frozen=True)
class UrbanNewsClue:
    publisher: str
    canonical_url: str
    source_class: str
    topics: tuple[str, ...]
    published_at: str | None
    headline: str


def normalize_clue(clue: UrbanNewsClue) -> dict[str, object]:
    parsed = urlparse(clue.canonical_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("news clue requires canonical HTTPS URL")
    if clue.source_class not in RECOGNIZED_CLASSES:
        raise ValueError("news clue publisher class is not governed")
    topics = tuple(sorted(set(clue.topics).intersection(PRIORITY_TOPICS)))
    if not topics:
        raise ValueError("news clue is outside targeted urban domains")
    return {
        "publisher": clue.publisher,
        "canonical_url": clue.canonical_url,
        "source_class": clue.source_class,
        "topics": list(topics),
        "published_at": clue.published_at,
        "headline": clue.headline,
        "role": "CLUE_ONLY_REQUIRES_INDEPENDENT_GOVERNED_CORROBORATION",
        "may_conclude": False,
        "may_create_signal": False,
    }

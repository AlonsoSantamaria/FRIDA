"""Metrobús GTFS-RT preparation contract, intentionally offline until access exists.

This module is not a live integration.  It normalises standards-shaped fixture
data, keeps observation provenance separate from operational state, and offers
an adapter that can later implement ``AuthorizedSnapshotProvider`` once
Metrobús supplies official credentials.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Any, Protocol

from .domain import EvidenceClass
from .observation import ReplaySnapshot


SOURCE_ID = "CDMX_METROBUS_GTFS_RT"
SOURCE_REFERENCE = "https://www.metrobus.cdmx.gob.mx/portal-ciudadano/datos-abiertos"


class MetrobusCredentialPending(RuntimeError):
    pass


class OperationalEligibilityPolicy(Protocol):
    def classify(self, previous: "MetrobusOperationalState", current: "MetrobusOperationalState") -> str: ...


@dataclass(frozen=True, slots=True)
class ObservationIdentity:
    source_id: str
    source_reference: str
    retrieved_at: datetime
    feed_header_timestamp: datetime | None
    feed_version: str | None


@dataclass(frozen=True, slots=True)
class MetrobusOperationalState:
    facts: dict[str, object]
    fingerprint_sha256: str


def _stamp(value: object) -> datetime | None:
    if value in (None, "", 0, "0"):
        return None
    return datetime.fromtimestamp(int(str(value)), tz=UTC)


def _aggregate(items: list[dict[str, str]]) -> list[dict[str, object]]:
    counts = Counter(tuple(sorted(item.items())) for item in items)
    return [dict(values, count=count) for values, count in sorted(counts.items())]


def normalise_gtfs_realtime(feed: Mapping[str, Any], *, retrieved_at: datetime | None = None) -> tuple[ObservationIdentity, MetrobusOperationalState]:
    """Reduce a GTFS-RT-shaped payload without retaining vehicle/entity IDs or traces."""
    header = feed.get("header") or {}
    if not isinstance(header, Mapping):
        raise ValueError("GTFS-RT header is required")
    vehicles: list[dict[str, str]] = []
    updates: list[dict[str, str]] = []
    alerts: list[dict[str, str]] = []
    for entity in feed.get("entity") or []:
        if not isinstance(entity, Mapping):
            continue
        vehicle = entity.get("vehicle")
        if isinstance(vehicle, Mapping):
            trip = vehicle.get("trip") or {}
            vehicles.append({"route_id": str(trip.get("route_id", "")), "direction_id": str(trip.get("direction_id", "")), "status": str(vehicle.get("current_status", "")), "stop_id": str(vehicle.get("stop_id", ""))})
        update = entity.get("trip_update")
        if isinstance(update, Mapping):
            trip = update.get("trip") or {}
            for stop in update.get("stop_time_update") or []:
                if isinstance(stop, Mapping):
                    updates.append({"route_id": str(trip.get("route_id", "")), "direction_id": str(trip.get("direction_id", "")), "stop_id": str(stop.get("stop_id", "")), "relationship": str(stop.get("schedule_relationship", ""))})
        alert = entity.get("alert")
        if isinstance(alert, Mapping):
            for informed in alert.get("informed_entity") or [{}]:
                if isinstance(informed, Mapping):
                    alerts.append({"effect": str(alert.get("effect", "")), "cause": str(alert.get("cause", "")), "route_id": str(informed.get("route_id", "")), "stop_id": str(informed.get("stop_id", ""))})
    facts = {"vehicles": _aggregate(vehicles), "trip_updates": _aggregate(updates), "alerts": _aggregate(alerts)}
    canonical = json.dumps(facts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    retrieved_at = retrieved_at or datetime.now(tz=UTC)
    identity = ObservationIdentity(SOURCE_ID, SOURCE_REFERENCE, retrieved_at, _stamp(header.get("timestamp")), str(header.get("gtfs_realtime_version")) or None)
    return identity, MetrobusOperationalState(facts, sha256(canonical).hexdigest())


def classify_operational_change(previous: MetrobusOperationalState | None, current: MetrobusOperationalState, policy: OperationalEligibilityPolicy | None = None) -> str:
    if previous is not None and previous.fingerprint_sha256 == current.fingerprint_sha256:
        return "SAME_STATE"
    if previous is None or policy is None:
        return "ORDINARY_CHANGE"
    return policy.classify(previous, current)


class MetrobusGtfsRtAdapter:
    """Future provider adapter; it fails closed until an official feed client is supplied."""

    def __init__(self, fetch_feed: Callable[[], Mapping[str, Any]] | None = None):
        self._fetch_feed = fetch_feed
        self._sequence = 0

    def snapshots(self) -> tuple[ReplaySnapshot, ...]:
        if self._fetch_feed is None:
            raise MetrobusCredentialPending("official Metrobús GTFS-RT access is pending")
        identity, state = normalise_gtfs_realtime(self._fetch_feed())
        self._sequence += 1
        source_date = identity.feed_header_timestamp or identity.retrieved_at
        return (ReplaySnapshot(SOURCE_ID, identity.source_reference, source_date, state.fingerprint_sha256, EvidenceClass.REAL, self._sequence, identity.retrieved_at),)

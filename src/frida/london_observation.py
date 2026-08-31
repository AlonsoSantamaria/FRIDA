"""Official, privacy-minimised London observation fabric.

The provider observes three bounded public sources.  It never creates a
Signal, Attention, Candidate, Case, or model invocation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TFL_VICTORIA = "LONDON_TFL_VICTORIA"
PLANNING_SW8 = "LONDON_PLANNING_SW8"
EA_THAMES_TIDEWAY = "LONDON_EA_THAMES_TIDEWAY"
GLA_HOUSING_LED = "LONDON_GLA_HOUSING_LED_SW8"
LONDON_SAFETY_MPS = "LONDON_MPS_BOROUGH_SAFETY_SW8"
TFL_URL = "https://api.tfl.gov.uk/Line/victoria/Status"
PLANNING_SEARCH_URL = "https://planningdata.london.gov.uk/api-guest/applications/_search"
EA_STATION_URL = "https://environment.data.gov.uk/flood-monitoring/id/stations/0006"
EA_MEASURE_URL = "https://environment.data.gov.uk/flood-monitoring/id/measures/0006-level-tidal_level-i-15_min-mAOD/readings?_limit=1"
CADENCES = {TFL_VICTORIA: 300, EA_THAMES_TIDEWAY: 900, PLANNING_SW8: 21600, GLA_HOUSING_LED: 86400, LONDON_SAFETY_MPS: 2592000}


@dataclass(frozen=True, slots=True)
class LondonSnapshot:
    source_id: str
    authority: str
    source_url: str
    retrieved_at: datetime
    source_timestamp: str | None
    geography: dict[str, object]
    canonical_state: dict[str, object]
    fingerprint_sha256: str
    adapter_version: str = "london-observation-v1"
    normalization_version: str = "london-normalization-v1"

    def persisted(self) -> dict[str, object]:
        return {
            "source_id": self.source_id, "authority": self.authority,
            "source_url": self.source_url, "retrieved_at": self.retrieved_at.isoformat(),
            "source_timestamp": self.source_timestamp, "geography": self.geography,
            "canonical_state": self.canonical_state, "fingerprint_sha256": self.fingerprint_sha256,
            "adapter_version": self.adapter_version, "normalization_version": self.normalization_version,
        }


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _snapshot(source_id: str, authority: str, source_url: str, source_timestamp: str | None, geography: dict[str, object], state: dict[str, object], retrieved_at: datetime | None = None) -> LondonSnapshot:
    return LondonSnapshot(source_id, authority, source_url, retrieved_at or datetime.now(tz=UTC), source_timestamp, geography, state, sha256(_canonical(state).encode()).hexdigest())


def normalize_tfl(payload: Sequence[Mapping[str, Any]], *, retrieved_at: datetime | None = None) -> LondonSnapshot:
    if not payload or not isinstance(payload[0], Mapping):
        raise ValueError("TfL Victoria response has no line state")
    line = payload[0]
    statuses = line.get("lineStatuses") or []
    status = statuses[0] if statuses and isinstance(statuses[0], Mapping) else {}
    state = {"line_id": str(line.get("id") or "victoria"), "line_name": str(line.get("name") or "Victoria"), "status": str(status.get("statusSeverityDescription") or ""), "status_severity": status.get("statusSeverity")}
    return _snapshot(TFL_VICTORIA, "Transport for London", TFL_URL, str(line.get("modified") or "") or None, {"coverage": "Vauxhall / Victoria line context", "kind": "urban accessibility"}, state, retrieved_at)


def normalize_planning(payload: Mapping[str, Any], *, retrieved_at: datetime | None = None) -> LondonSnapshot:
    hits = ((payload.get("hits") or {}).get("hits") or []) if isinstance(payload, Mapping) else []
    if not isinstance(hits, Sequence):
        raise ValueError("Planning London Datahub response has no hits")
    records=[]
    timestamps=[]
    for hit in hits:
        source = hit.get("_source", {}) if isinstance(hit, Mapping) else {}
        if not isinstance(source, Mapping):
            continue
        record={"application_id": str(source.get("id") or hit.get("_id") or ""), "status": str(source.get("applicationStatus") or source.get("status") or ""), "decision_date": str(source.get("decisionDate") or ""), "actual_start_date": str(source.get("actualCommencementDate") or ""), "actual_completion_date": str(source.get("actualCompletionDate") or ""), "development_type": str(source.get("developmentType") or "")}
        if record["application_id"]:
            records.append(record)
        for key in ("lastUpdated", "lastUpdatedDate", "updateDate"):
            if source.get(key): timestamps.append(str(source[key]))
    records.sort(key=lambda item: item["application_id"])
    state={"postcode": "SW8", "records": records}
    return _snapshot(PLANNING_SW8, "Greater London Authority Planning London Datahub", PLANNING_SEARCH_URL, max(timestamps) if timestamps else None, {"coverage": "Wandsworth SW8 / Battersea–Nine Elms–Vauxhall", "kind": "development lifecycle"}, state, retrieved_at)


def normalize_environment(station: Mapping[str, Any], readings: Mapping[str, Any], *, retrieved_at: datetime | None = None) -> LondonSnapshot:
    items = readings.get("items") or []
    latest = items[0] if items and isinstance(items[0], Mapping) else {}
    state={"station_id": "0006", "measure_id": "0006-level-tidal_level-i-15_min-mAOD", "value": latest.get("value"), "unit": "mAOD"}
    timestamp = str(latest.get("dateTime") or latest.get("dateTimeUTC") or "") or None
    return _snapshot(EA_THAMES_TIDEWAY, "Environment Agency", EA_STATION_URL, timestamp, {"coverage": "Thames Tideway / Westminster context", "kind": "hydrological context"}, state, retrieved_at)


class LondonObservationFabricProvider:
    """Read-only bounded public-source acquisition with persisted scheduling."""
    cadences = CADENCES

    def __init__(self, fetch: Callable[..., object] | None = None, due_source_ids: Callable[[], Sequence[str]] | None = None, source_completed: Callable[[str, str | None], None] | None = None):
        self._fetch = fetch or self._http_fetch
        self._due_source_ids = due_source_ids or (lambda: tuple(CADENCES))
        self._source_completed = source_completed or (lambda _source_id, _error: None)

    @staticmethod
    def _http_fetch(url: str, *, method: str = "GET", payload: Mapping[str, object] | None = None, headers: Mapping[str, str] | None = None) -> object:
        request_headers={"Accept": "application/json", "User-Agent": "FRIDA/1.0 official-observation"}
        request_headers.update(headers or {})
        data=json.dumps(payload).encode() if payload is not None else None
        request=Request(url, data=data, method=method, headers=request_headers)
        with urlopen(request, timeout=45) as response:  # nosec B310: fixed official HTTPS sources
            return json.loads(response.read().decode("utf-8"))

    def snapshots(self) -> tuple[LondonSnapshot, ...]:
        now=datetime.now(tz=UTC); snapshots=[]
        for source_id in self._due_source_ids():
            try:
                if source_id == TFL_VICTORIA:
                    key=os.environ.get("FRIDA_TFL_APP_KEY")
                    # The bounded status endpoint supports a public anonymous
                    # read.  Cloud Run still uses its bound key when present;
                    # a fresh local verification must not fail solely because
                    # that secret is intentionally not copied into a process.
                    url=TFL_URL + ("?" + urlencode({"app_key": key}) if key else "")
                    payload=self._fetch(url)
                    snapshot=normalize_tfl(payload, retrieved_at=now)
                elif source_id == PLANNING_SW8:
                    payload=self._fetch(PLANNING_SEARCH_URL, method="POST", headers={"Content-Type":"application/json", "X-API-AllowRequest":"FRIDA"}, payload={"size":50,"query":{"match_phrase":{"postcode":"SW8"}},"_source":["id","applicationStatus","status","decisionDate","actualCommencementDate","actualCompletionDate","developmentType","lastUpdated"]})
                    snapshot=normalize_planning(payload, retrieved_at=now)
                elif source_id == EA_THAMES_TIDEWAY:
                    station=self._fetch(EA_STATION_URL); readings=self._fetch(EA_MEASURE_URL)
                    snapshot=normalize_environment(station, readings, retrieved_at=now)
                elif source_id == GLA_HOUSING_LED:
                    from .london_housing import fetch_housing_led
                    snapshot=fetch_housing_led()
                elif source_id == LONDON_SAFETY_MPS:
                    from .london_safety import fetch_mps_borough_safety
                    snapshot=fetch_mps_borough_safety()
                else:
                    continue
            except Exception as error:
                self._source_completed(source_id, type(error).__name__)
                continue
            self._source_completed(source_id, None)
            snapshots.append(snapshot)
        return tuple(snapshots)

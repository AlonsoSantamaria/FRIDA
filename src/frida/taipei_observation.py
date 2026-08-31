"""Taipei's minimum official operational observation fabric.

This adapter is deterministic.  It records provenance separately from a
privacy-minimised operational state and never creates a Signal by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from urllib.request import Request, urlopen
from typing import Any, Mapping, Sequence


TAIPEI_WORKS = "TAIPEI_ACTIVE_PUBLIC_WORKS"
TAIPEI_RAIN = "TAIPEI_REALTIME_RAINFALL"
TAIPEI_DRAINAGE = "TAIPEI_REALTIME_DRAINAGE"

WORKS_URL = "https://tpnco.blob.core.windows.net/blobfs/Todaywork.json"
# These official public endpoints are injected by runtime configuration; their
# catalog access parameters are deliberately never rendered, logged, or stored.
RAIN_ENDPOINT = "https://wic.gov.taipei/OpenData/API/Rain/Get"
DRAINAGE_ENDPOINT = "https://wic.gov.taipei/OpenData/API/Sewer/Get"
RAIN_FETCH_URL = RAIN_ENDPOINT + "?stationNo=&loginId=open_rain&dataKey=85452C1D"
DRAINAGE_FETCH_URL = DRAINAGE_ENDPOINT + "?stationNo=&loginId=sewer01&dataKey=BD3E513A"
WORKS_CATALOG_URL = "https://data.taipei/dataset/detail?id=c208dabd-2da0-4e6d-8dbd-a004b9782b0a"
RAIN_CATALOG_URL = "https://data.taipei/dataset/detail?id=6f03a0b8-7b98-4eea-8bb9-ba6bfcdc2b8b"
DRAINAGE_CATALOG_URL = "https://data.taipei/dataset/detail?id=cd444840-bbfb-4b0a-bdfa-2a36d49b3794"


@dataclass(frozen=True, slots=True)
class TaipeiSnapshot:
    source_id: str
    authority: str
    source_url: str
    retrieved_at: datetime
    source_timestamp: str | None
    geography: dict[str, object]
    canonical_state: dict[str, object]
    fingerprint_sha256: str
    adapter_version: str = "taipei-observation-v1"
    normalization_version: str = "taipei-normalization-v1"

    def persisted(self) -> dict[str, object]:
        return {
            "source_id": self.source_id,
            "authority": self.authority,
            "source_url": self.source_url,
            "retrieved_at": self.retrieved_at.isoformat(),
            "source_timestamp": self.source_timestamp,
            "geography": self.geography,
            "canonical_state": self.canonical_state,
            "fingerprint_sha256": self.fingerprint_sha256,
            "adapter_version": self.adapter_version,
            "normalization_version": self.normalization_version,
        }


def _canonical(value: Mapping[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _snapshot(source_id: str, source_url: str, timestamp: str | None, geography: dict[str, object], state: dict[str, object], retrieved_at: datetime | None) -> TaipeiSnapshot:
    retrieved_at = retrieved_at or datetime.now(tz=UTC)
    return TaipeiSnapshot(
        source_id=source_id,
        authority="Taipei City Government",
        source_url=source_url,
        retrieved_at=retrieved_at,
        source_timestamp=timestamp,
        geography=geography,
        canonical_state=state,
        fingerprint_sha256=sha256(_canonical(state).encode("utf-8")).hexdigest(),
    )


def normalize_works(payload: Mapping[str, Any], *, retrieved_at: datetime | None = None) -> TaipeiSnapshot:
    """Normalise the official GeoJSON while dropping names and contacts."""
    features = payload.get("features")
    if not isinstance(features, Sequence):
        raise ValueError("Taipei works feed must be a GeoJSON FeatureCollection")
    works: list[dict[str, object]] = []
    stamps: list[str] = []
    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        props = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(props, Mapping) or not isinstance(geometry, Mapping):
            continue
        application_time = str(props.get("AppTime") or "")
        if application_time:
            stamps.append(application_time)
        # Specifically exclude App_Name, C_Name, Tc_Na, Tc_Ma, Tc_Tl,
        # Tc_Ma3 and Tc_Tl3: applicant/company and named contact data.
        works.append({
            "work_id": str(props.get("Ac_no") or ""),
            "work_type": str(props.get("WItem") or props.get("DType") or ""),
            "purpose": str(props.get("NPurp") or ""),
            "address": str(props.get("Addr") or ""),
            "start_date": str(props.get("Cb_Da") or ""),
            "end_date": str(props.get("Ce_Da") or ""),
            "traffic_blocked": str(props.get("IsBlock") or ""),
            "traffic_stayed": str(props.get("IsStay") or ""),
            "length_m": str(props.get("DLen") or ""),
            "geometry": geometry,
        })
    works.sort(key=lambda item: str(item["work_id"]))
    state = {"active_works": works}
    return _snapshot(TAIPEI_WORKS, WORKS_URL, max(stamps) if stamps else None, {"kind": "work_location", "coverage": "Taipei City"}, state, retrieved_at)


def _normalize_stations(source_id: str, source_url: str, payload: Mapping[str, Any], value_key: str, *, retrieved_at: datetime | None = None) -> TaipeiSnapshot:
    rows = payload.get("data")
    if not isinstance(rows, Sequence):
        raise ValueError("Taipei real-time feed must contain a data array")
    stations: list[dict[str, object]] = []
    stamps: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        stamp = str(row.get("recTime") or "")
        if stamp:
            stamps.append(stamp)
        stations.append({
            "station_id": str(row.get("stationNo") or ""),
            "station_name": str(row.get("stationName") or ""),
            "observed_value": row.get(value_key),
        })
    stations.sort(key=lambda item: str(item["station_id"]))
    state = {"stations": stations, "metric": value_key}
    return _snapshot(source_id, source_url, max(stamps) if stamps else None, {"kind": "station", "coverage": "Taipei City"}, state, retrieved_at)


def normalize_rainfall(payload: Mapping[str, Any], *, source_url: str = RAIN_ENDPOINT, retrieved_at: datetime | None = None) -> TaipeiSnapshot:
    return _normalize_stations(TAIPEI_RAIN, source_url, payload, "rain", retrieved_at=retrieved_at)


def normalize_drainage(payload: Mapping[str, Any], *, source_url: str = DRAINAGE_ENDPOINT, retrieved_at: datetime | None = None) -> TaipeiSnapshot:
    return _normalize_stations(TAIPEI_DRAINAGE, source_url, payload, "levelOut", retrieved_at=retrieved_at)


def classify_state(previous_fingerprint: str | None, current: TaipeiSnapshot) -> str:
    """First-cycle and non-identical states remain deterministic ordinary change."""
    if previous_fingerprint == current.fingerprint_sha256:
        return "SAME_STATE"
    return "ORDINARY_CHANGE"


class TaipeiObservationFabricProvider:
    """Read-only official source acquisition, with no semantic dispatch."""
    def __init__(self, fetch=None):
        self._fetch = fetch or self._http_fetch

    @staticmethod
    def _http_fetch(url: str) -> Mapping[str, Any]:
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "FRIDA/1.0 official-observation-probe"})
        with urlopen(request, timeout=45) as response:  # nosec B310: fixed official HTTPS endpoints
            body = response.read().decode("utf-8-sig")
        parsed = json.loads(body)
        if not isinstance(parsed, Mapping):
            raise ValueError("official Taipei source did not return a JSON object")
        return parsed

    def snapshots(self) -> tuple[TaipeiSnapshot, ...]:
        now = datetime.now(tz=UTC)
        return (
            normalize_works(self._fetch(WORKS_URL), retrieved_at=now),
            normalize_rainfall(self._fetch(RAIN_FETCH_URL), source_url=RAIN_CATALOG_URL, retrieved_at=now),
            normalize_drainage(self._fetch(DRAINAGE_FETCH_URL), source_url=DRAINAGE_CATALOG_URL, retrieved_at=now),
        )

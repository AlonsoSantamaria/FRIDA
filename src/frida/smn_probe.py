"""Read-only SMN/CONAGUA municipal forecast probe; not an observation adapter.

It deliberately returns a normalised source state without persisting it or
creating a Signal.  Product/Architecture must separately approve any source
adapter, eligibility policy, cadence, or scheduler.
"""
from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import gzip
import json
from typing import Any
from urllib.request import Request, urlopen


SMN_MUNICIPAL_FORECAST_URL = "https://smn.conagua.gob.mx/tools/GUI/webservices/?method=1"
QUERETARO_STATE_ID = "22"
QUERETARO_MUNICIPALITY_ID = "14"
SOURCE_ID = "SMN_CONAGUA_MUNICIPAL_FORECAST_QRO"

_FIELDS = ("dloc", "ndia", "tmax", "tmin", "desciel", "probprec", "prec", "velvien", "dirvienc", "dirvieng", "raf", "cc")


class SMNProbeError(RuntimeError):
    pass


def normalise_queretaro(records: list[dict[str, Any]], *, retrieved_at: datetime | None = None) -> dict[str, object]:
    """Select official municipality identity and make a stable comparison state."""
    selected = [row for row in records if str(row.get("ides")) == QUERETARO_STATE_ID and str(row.get("idmun")) == QUERETARO_MUNICIPALITY_ID]
    if not selected:
        raise SMNProbeError("SMN response did not contain Querétaro municipality 22/14")
    days = [{field: str(row.get(field, "")).strip() for field in _FIELDS} for row in selected]
    days.sort(key=lambda row: (int(row["ndia"] or 0), row["dloc"]))
    identity = {"source_id": SOURCE_ID, "state_id": QUERETARO_STATE_ID, "municipality_id": QUERETARO_MUNICIPALITY_ID, "forecast": days}
    canonical = json.dumps(identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    retrieved_at = retrieved_at or datetime.now(tz=UTC)
    return {
        **identity,
        "source_reference": SMN_MUNICIPAL_FORECAST_URL,
        "source_forecast_dates": [row["dloc"] for row in days],
        "retrieved_at": retrieved_at.isoformat(),
        "content_fingerprint_sha256": sha256(canonical).hexdigest(),
        "source_state_timestamp": max(row["dloc"] for row in days),
    }


def classify_source_state(previous: dict[str, object], current: dict[str, object]) -> str:
    return "SAME_SOURCE_STATE" if previous["content_fingerprint_sha256"] == current["content_fingerprint_sha256"] else "SOURCE_STATE_CHANGED"


def probe_queretaro_forecast(*, timeout_seconds: float = 20.0) -> dict[str, object]:
    """One public-source request, decompressed in memory, without persistence."""
    request = Request(SMN_MUNICIPAL_FORECAST_URL, headers={"Accept-Encoding": "gzip", "User-Agent": "FRIDA-SMN-read-only-probe/1.0"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
            payload = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    except Exception as error:
        raise SMNProbeError(f"SMN transport unavailable: {type(error).__name__}") from error
    try:
        records = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SMNProbeError(f"SMN response was not valid JSON: {type(error).__name__}") from error
    if not isinstance(records, list):
        raise SMNProbeError("SMN response root was not a forecast list")
    return normalise_queretaro(records)

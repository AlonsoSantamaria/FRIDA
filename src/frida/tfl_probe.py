"""Bounded, private Transport for London connectivity probe.

This is not an observation provider.  It verifies one official, geographic
transport context without persisting a Signal, Case, or any passenger data.
"""
from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Callable, Mapping
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TFL_VICTORIA_STATUS_URL = "https://api.tfl.gov.uk/Line/victoria/Status"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def probe_victoria_line(
    app_key: str | None = None,
    *,
    fetch: Callable[[str], tuple[int, Mapping[str, str], object]] | None = None,
) -> dict[str, object]:
    """Return sanitized, deterministic TfL state for the Vauxhall context."""
    url = TFL_VICTORIA_STATUS_URL
    if app_key:
        url += "?" + urlencode({"app_key": app_key})

    if fetch is None:
        def fetch(request_url: str) -> tuple[int, Mapping[str, str], object]:
            request = Request(request_url, headers={"Accept": "application/json", "User-Agent": "FRIDA/1.0 bounded-probe"})
            with urlopen(request, timeout=20) as response:  # nosec B310: fixed official HTTPS endpoint
                return response.status, dict(response.headers.items()), json.loads(response.read().decode("utf-8"))

    status, headers, payload = fetch(url)
    if status != 200 or not isinstance(payload, list) or not payload:
        raise RuntimeError("TfL official endpoint did not return a usable status payload")
    line = payload[0]
    if not isinstance(line, Mapping):
        raise RuntimeError("TfL status payload has an unexpected shape")
    states = line.get("lineStatuses", [])
    state = states[0] if isinstance(states, list) and states and isinstance(states[0], Mapping) else {}
    normalized = {
        "line_id": str(line.get("id", "")),
        "line_name": str(line.get("name", "")),
        "status": str(state.get("statusSeverityDescription", "")),
        "status_severity": state.get("statusSeverity"),
        "modified": str(line.get("modified", "")),
        "context": "Vauxhall / Victoria line",
    }
    return {
        "source": "Transport for London Unified API",
        "endpoint": TFL_VICTORIA_STATUS_URL,
        "retrieved_at": datetime.now(tz=UTC).isoformat(),
        "source_timestamp": normalized["modified"] or None,
        "credential_mode": "REGISTERED_KEY" if app_key else "ANONYMOUS_BOUNDED_PROBE",
        "http_status": status,
        "rate_limit_headers": {key: value for key, value in headers.items() if key.lower().startswith("x-ratelimit")},
        "normalized_state": normalized,
        "state_fingerprint_sha256": sha256(_canonical(normalized).encode("utf-8")).hexdigest(),
        "model_calls": 0,
        "personal_data_processed": False,
    }

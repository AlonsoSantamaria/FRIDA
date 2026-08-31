"""Deterministic governed ingestion for the frozen water-resilience bundle.

This module deliberately performs no scenario reasoning, semantic runtime, or
forecasting.  It turns a pinned public-evidence package into an append-only
source state and evaluates only the frozen eligibility prerequisites.
"""
from __future__ import annotations

import csv
import hashlib
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .persistence import StagingStore


BUNDLE_ID = "FORESIGHT-WR-2201-v1"
SOURCE_STATE_ID = "foresight-source-state-wr-2201-v1-2026-08-25"
SCENARIO_INPUT_SET_ID = "scenario-input-wr-2201-v1"
CONTRACT_VERSION = "FRIDA_FORESIGHT_CONTRACT_v1.0"
GEOGRAPHY = "Valle de Queretaro aquifer (2201); Municipality of Queretaro is qualified planning context only"
GEOGRAPHIC_CONFIDENCE = "EXACT_SOURCE_DEFINED_AREA"
HORIZON = "12_MONTHS"
COMPUTATION_MODE = "QUALITATIVE"


@dataclass(frozen=True, slots=True)
class SourceSpec:
    source_id: str
    relative_path: str
    sha256: str
    source_date: str
    geography: str
    temporal_reference: str
    classification: str = "OBSERVED"


@dataclass(frozen=True, slots=True)
class Assumption:
    assumption_id: str
    variant: str
    statement: str
    classification: str = "ASSUMED"


SOURCE_SPECS = (
    SourceSpec("FW-CONAGUA-DR-2201-2024", "raw/conagua_dr_2201_2024.pdf", "170fb8c5837ea57763bdc47a4a8f85bd58b8d90fc441297460e02426b181e2c7", "2024", "Valle de Queretaro aquifer (2201)", "2024 annual aquifer availability update"),
    SourceSpec("FW-MQRO-ANUARIO-2025", "raw/municipio_queretaro_anuario_economico_2025.html", "03cd44d9a701af0ad321c3b41c384d026c0d4f218e4f6f7d7bf4992fbb043050", "2025", "Municipality of Queretaro", "2024 population-change context"),
    SourceSpec("FW-CONAGUA-AVAILABILITY-GEOMETRY-2020", "raw/conagua_disponibilidad_agua_por_acuifero.zip", "718ddc03c5516d230d22bbaff5d69ec6fe951876454b365520ea830d1608b62f", "2020", "National aquifer geometry", "Historical geometry reference only"),
)

ASSUMPTIONS = (
    Assumption("ASM-WR-BASELINE-001", "BASELINE", "The governed aquifer-level deficit remains an active planning constraint during the bounded horizon."),
    Assumption("ASM-WR-STRESS-001", "STRESS", "Additional demand pressure or reduced flexibility occurs during the bounded horizon; no magnitude, cause, or probability is asserted."),
    Assumption("ASM-WR-MITIGATION-001", "MITIGATION", "Relevant authorities conduct a bounded review of demand-management, reuse, recharge, and contingency options; no effectiveness or implementation is asserted."),
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_facts(root: Path) -> list[dict[str, str]]:
    path = root / "normalized" / "observed_facts_v1.csv"
    if not path.is_file():
        raise ValueError("foresight normalized facts file is missing")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    expected = {"FW-OBS-001", "FW-OBS-002", "FW-OBS-003", "FW-OBS-004", "FW-OBS-005"}
    if {row.get("fact_id") for row in rows} != expected:
        raise ValueError("foresight normalized facts have an unexpected identity set")
    if any(row.get("observation_status") != "OBSERVED" for row in rows):
        raise ValueError("foresight normalized facts must preserve OBSERVED classification")
    if any(row.get("source_id") not in {spec.source_id for spec in SOURCE_SPECS} for row in rows):
        raise ValueError("foresight normalized facts reference an ungoverned source")
    return rows


def build_scenario_input_set(source_state_id: str) -> dict[str, object]:
    """Build the immutable qualitative input-set; no future fact is implied."""
    return {
        "scenario_input_set_id": SCENARIO_INPUT_SET_ID,
        "bundle_id": BUNDLE_ID,
        "source_state_id": source_state_id,
        "contract_version": CONTRACT_VERSION,
        "authorization_reference": "FORESIGHT_CONTRACT_FREEZE_AND_INGESTION_CLEARANCE_2026-08-25",
        "request_source": "HUMAN_REQUESTED",
        "horizon": HORIZON,
        "computation_mode": COMPUTATION_MODE,
        "geography": GEOGRAPHY,
        "geographic_confidence": GEOGRAPHIC_CONFIDENCE,
        "scenario_definitions": (
            {"scenario_definition_id": "SCN-WR-BASELINE-v1", "variant": "BASELINE", "changed_assumption_ids": ("ASM-WR-BASELINE-001",)},
            {"scenario_definition_id": "SCN-WR-STRESS-v1", "variant": "STRESS", "parent_id": "SCN-WR-BASELINE-v1", "changed_assumption_ids": ("ASM-WR-BASELINE-001", "ASM-WR-STRESS-001")},
            {"scenario_definition_id": "SCN-WR-MITIGATION-v1", "variant": "MITIGATION", "parent_id": "SCN-WR-BASELINE-v1", "changed_assumption_ids": ("ASM-WR-BASELINE-001", "ASM-WR-MITIGATION-001")},
        ),
        "assumptions": tuple(asdict(item) for item in ASSUMPTIONS),
        "prohibited_derivations": (
            "future extraction", "future recharge", "municipal water demand", "future deficit",
            "probability", "supply failure", "population-to-water conversion", "mitigation magnitude",
        ),
    }


def evaluate_eligibility(source_state: dict[str, object], input_set: dict[str, object]) -> dict[str, object]:
    """Frozen deterministic eligibility, intentionally separate from runtime."""
    reasons: list[str] = []
    if not source_state.get("integrity_verified"):
        reasons.append("SOURCE_HASH_OR_PROVENANCE_INVALID")
    if source_state.get("bundle_id") != BUNDLE_ID:
        reasons.append("BUNDLE_ID_MISMATCH")
    if input_set.get("source_state_id") != source_state.get("source_state_id"):
        reasons.append("SOURCE_STATE_REFERENCE_INVALID")
    if input_set.get("horizon") != HORIZON:
        reasons.append("HORIZON_INVALID")
    if input_set.get("computation_mode") != COMPUTATION_MODE:
        reasons.append("COMPUTATION_MODE_INVALID")
    if input_set.get("geographic_confidence") != GEOGRAPHIC_CONFIDENCE:
        reasons.append("GEOGRAPHY_INVALID")
    assumptions = input_set.get("assumptions", ())
    if {item.get("classification") for item in assumptions if isinstance(item, dict)} != {"ASSUMED"} or len(assumptions) != 3:
        reasons.append("ASSUMPTION_TRACEABILITY_INVALID")
    variants = input_set.get("scenario_definitions", ())
    if {item.get("variant") for item in variants if isinstance(item, dict)} != {"BASELINE", "STRESS", "MITIGATION"}:
        reasons.append("SCENARIO_VARIANTS_INCOMPLETE")
    status = "ELIGIBLE" if not reasons else "NOT_ELIGIBLE"
    return {"status": status, "reasons": tuple(reasons), "gate": "FORESIGHT_ELIGIBILITY_GATE"}


def ingest_water_resilience_bundle(store: StagingStore, evidence_root: str | Path) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Verify files first, then append the source state and its eligible input set."""
    root = Path(evidence_root)
    verified_sources: list[dict[str, str]] = []
    for spec in SOURCE_SPECS:
        path = root / spec.relative_path
        if not path.is_file() or _hash(path) != spec.sha256:
            raise ValueError(f"foresight source integrity check failed: {spec.source_id}")
        verified_sources.append(asdict(spec))
    facts = _normalized_facts(root)
    source_state = {
        "source_state_id": SOURCE_STATE_ID,
        "bundle_id": BUNDLE_ID,
        "contract_version": CONTRACT_VERSION,
        "integrity_verified": True,
        "geography": GEOGRAPHY,
        "geographic_confidence": GEOGRAPHIC_CONFIDENCE,
        "temporal_reference": "2020 historical geometry; 2024 aquifer condition and municipal planning context; 12-month scenario horizon is assumed, not observed",
        "sources": verified_sources,
        "facts": facts,
        "created_at": datetime.now(UTC).isoformat(),
    }
    input_set = build_scenario_input_set(SOURCE_STATE_ID)
    decision = evaluate_eligibility(source_state, input_set)
    store.create_foresight_source_state(source_state)
    store.create_foresight_scenario_input_set(input_set, decision)
    return source_state, input_set, decision

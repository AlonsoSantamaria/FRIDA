"""Governed execution instances over historical evidence, without new observation semantics."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .domain import Evidence
from .observation import CandidateSignal
from .persistence import StagingStore

EXECUTION_MODE = "CONTROLLED_REPLAY_DEMO"
SOURCE_OBSERVATION_MODE = "HISTORICAL_REAL"
SCENARIO_CONTRACT_VERSION = "FRIDA_DEMO_SCENARIO_EVIDENCE_CONTRACT_v1.1"
ORIGINAL_EXECUTION_REFERENCE = "docs/stages/FRIDA_FIRST_GOLDEN_PATH_EXECUTION_EVIDENCE_v1.0.md"


@dataclass(frozen=True, slots=True)
class ControlledReplayExecution:
    execution_id: str
    created_at: datetime
    source_id: str
    source_hash: str
    candidate_signal_id: str
    evidence_hashes: dict[str, str]
    authorization_reference: str
    original_execution_reference: str = ORIGINAL_EXECUTION_REFERENCE
    execution_mode: str = EXECUTION_MODE
    source_observation_mode: str = SOURCE_OBSERVATION_MODE
    scenario_contract_version: str = SCENARIO_CONTRACT_VERSION

    def as_ledger_row(self) -> dict[str, object]:
        return asdict(self)


def evidence_hashes(evidence: Iterable[Evidence]) -> dict[str, str]:
    hashes = {item.evidence_id: item.content_hash for item in evidence}
    if not hashes or any(len(value) != 64 for value in hashes.values()):
        raise ValueError("controlled replay requires a complete immutable evidence bundle")
    return hashes


def verify_file_hashes(project_root: str | Path, expected: dict[str, str]) -> None:
    """Re-verify the approved on-disk WP01 evidence before a future runtime call."""
    root = Path(project_root)
    locations = {
        "wp01-s1-0525": root / "data/source-validation/wp01/denue/raw/denue_22_0525_csv.zip",
        "wp01-s1-0526": root / "data/source-validation/wp01/denue/raw/denue_22_0526_corrected_csv.zip",
        "wp01-s2-felix": root / "data/source-validation/wp01/s2_implan_felix_osores_map.pdf",
        "wp01-s3-semaforo": root / "data/source-validation/wp01/s3_puertas_de_san_miguel_stages_2026.csv",
    }
    if set(expected) != set(locations):
        raise ValueError("unexpected controlled replay evidence bundle")
    for evidence_id, path in locations.items():
        actual = sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != expected[evidence_id]:
            raise ValueError(f"controlled replay evidence hash mismatch: {evidence_id}")


def new_execution(candidate: CandidateSignal, evidence: tuple[Evidence, ...], authorization_reference: str, now: datetime | None = None) -> ControlledReplayExecution:
    if not authorization_reference.strip():
        raise ValueError("controlled replay requires an explicit authorization reference")
    now = now or datetime.now(tz=UTC)
    return ControlledReplayExecution(
        execution_id="exec-controlled-replay-" + uuid4().hex,
        created_at=now,
        source_id=candidate.source_id,
        source_hash=candidate.observed_hash,
        candidate_signal_id=candidate.signal_id,
        evidence_hashes=evidence_hashes(evidence),
        authorization_reference=authorization_reference,
    )


def register_execution_attempt(store: StagingStore, execution: ControlledReplayExecution, project_root: str | Path) -> None:
    """Register only a new execution identity after integrity verification; no model is invoked."""
    verify_file_hashes(project_root, execution.evidence_hashes)
    store.create_controlled_replay_execution(execution.as_ledger_row())
    store.append_execution_event(
        execution.execution_id, execution.created_at, "execution.registered",
        {"execution_mode": EXECUTION_MODE, "source_observation_mode": SOURCE_OBSERVATION_MODE,
         "claims_new_world_observation": False},
    )

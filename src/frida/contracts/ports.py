"""Provisional ports for reversible local experiments.

The protocols intentionally avoid committing to SQLite, Firestore, Pub/Sub,
ADK, or any other runtime implementation.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeVar


RecordT = TypeVar("RecordT")


class Repository(Protocol[RecordT]):
    def get(self, record_id: str) -> RecordT | None: ...

    def save(self, record: RecordT) -> None: ...


class EventPublisher(Protocol):
    def publish(self, event: object) -> None: ...


class SourceAdapter(Protocol):
    def collect(self) -> Iterable[object]: ...


class ModelGateway(Protocol):
    def generate_structured(self, *, instruction: str, schema: type[RecordT]) -> RecordT: ...


"""The scheduler-to-observer boundary; no scheduler or external source lives here.

An authorized source adapter supplies immutable snapshots.  The trigger hands
them to the existing deterministic observation cycle, which decides whether
semantic attention is justified.  This deliberately keeps a timer/fire event
from becoming a semantic model call.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol

from .observation import ReplaySnapshot


class AuthorizedSnapshotProvider(Protocol):
    """Future approved-source adapter contract; acquisition is outside FRIDA core."""

    def snapshots(self) -> Iterable[ReplaySnapshot]: ...


class ObservationTrigger:
    """One scheduler-safe wake-up boundary, with no retry or source selection."""

    def __init__(self, cycle_factory: Callable[[Callable[[], Iterable[ReplaySnapshot]]], object], provider: AuthorizedSnapshotProvider):
        self._cycle_factory = cycle_factory
        self._provider = provider

    def run_once(self) -> dict[str, object]:
        cycle = self._cycle_factory(self._provider.snapshots)
        return cycle.run_once()

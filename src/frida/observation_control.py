"""Small, source-independent operational control for FRIDA observation.

The clock wakes deterministic observation only.  It never dispatches Gemini,
and it deliberately pauses on an adapter failure instead of retrying it.
"""
from __future__ import annotations

from datetime import UTC, datetime
from threading import Event, Thread
from typing import Callable

from .observation_boundary import ObservationTrigger

MIN_CADENCE_SECONDS = 60
MAX_CADENCE_SECONDS = 86_400
DEFAULT_CADENCE_SECONDS = 300


def validate_cadence(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("observation cadence must be an integer number of seconds")
    try:
        cadence = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("observation cadence must be an integer number of seconds") from error
    if not MIN_CADENCE_SECONDS <= cadence <= MAX_CADENCE_SECONDS:
        raise ValueError(f"observation cadence must be between {MIN_CADENCE_SECONDS} and {MAX_CADENCE_SECONDS} seconds")
    return cadence


class AutonomousObservationController:
    """One lightweight worker per process; the store lease makes cycles global."""

    def __init__(self, store, cycle_factory: Callable, provider=None, *, poll_seconds: float = 1.0):
        self.store = store
        self._cycle_factory = cycle_factory
        self._provider = provider
        self._poll_seconds = poll_seconds
        self._stop = Event()
        self._thread: Thread | None = None

    @property
    def provider_configured(self) -> bool:
        return self._provider is not None

    def start_worker(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = Thread(target=self._run, name="frida-observation-control", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.wait(self._poll_seconds):
            try:
                control = self.store.observation_control()
            except Exception:
                # Service shutdown owns store closure.  A background worker must
                # never resurrect or mutate a closed execution context.
                return
            if control["state"] != "RUNNING":
                continue
            if self._provider is None:
                self.store.set_observation_source_health("NO_AUTHORIZED_SOURCE_CONFIGURED")
                continue
            if not self.store.claim_due_observation_cycle(datetime.now(tz=UTC)):
                continue
            try:
                trigger = ObservationTrigger(self._cycle_factory, self._provider)
                outcome = trigger.run_once()
            except Exception as error:  # Adapter failure is terminal until an operator resumes.
                self.store.finish_observation_cycle_claim(
                    datetime.now(tz=UTC), source_health="ERROR", error_class=type(error).__name__, pause=True
                )
            else:
                self.store.finish_observation_cycle_claim(
                    datetime.now(tz=UTC), source_health="HEALTHY", outcome=outcome
                )

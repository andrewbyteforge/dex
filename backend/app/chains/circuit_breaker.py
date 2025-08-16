# backend/app/chains/circuit_breaker.py
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreaker:
    """Simple circuit breaker with cooldown and half-open probe.

    The breaker opens after `failure_threshold` consecutive failures.
    It stays open for `cooldown_seconds`, after which it moves to HALF_OPEN
    and allows a single probe. If the probe succeeds, it closes; if it fails, it
    opens again and the cooldown resets.
    """
    failure_threshold: int = 3
    cooldown_seconds: float = 30.0

    _state: CircuitState = CircuitState.CLOSED
    _consecutive_failures: int = 0
    _opened_at: float | None = None
    _allow_half_open_probe: bool = True

    def on_success(self) -> None:
        self._consecutive_failures = 0
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._allow_half_open_probe = True

    def on_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            self._allow_half_open_probe = True

    def can_call(self) -> bool:
        now = time.monotonic()
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            if self._opened_at is None:
                return False
            if (now - self._opened_at) >= self.cooldown_seconds:
                self._state = CircuitState.HALF_OPEN
                # allow one probe attempt
                return self._allow_half_open_probe
            return False
        # HALF_OPEN
        return self._allow_half_open_probe

    def record_probe_attempt(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._allow_half_open_probe = False

    def state(self) -> CircuitState:
        return self._state

    def snapshot(self) -> dict:
        return {
            "state": self._state,
            "consecutive_failures": self._consecutive_failures,
            "cooldown_seconds": self.cooldown_seconds,
        }

"""Command-timeout watchdog that never blocks or starts threads itself."""

import time
from collections.abc import Callable
from enum import Enum


class WatchdogStatus(str, Enum):
    """Externally visible watchdog state."""

    IDLE = "idle"
    ARMED = "armed"
    TIMED_OUT = "timed_out"


class CommandWatchdog:
    """Detect missing command refreshes.

    The watchdog is passive: a caller feeds it on each valid command and polls
    ``check`` periodically. The clock is injectable so timing is testable.
    """

    def __init__(
        self,
        timeout_s: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("Watchdog timeout must be positive.")
        self._timeout_s = timeout_s
        self._clock = clock
        self._last_fed_at: float | None = None
        self._status = WatchdogStatus.IDLE

    @property
    def timeout_s(self) -> float:
        """Return the configured timeout in seconds."""
        return self._timeout_s

    @property
    def status(self) -> WatchdogStatus:
        """Return the current watchdog status."""
        return self._status

    def feed(self) -> None:
        """Record a valid command and (re)arm the watchdog."""
        self._last_fed_at = self._clock()
        self._status = WatchdogStatus.ARMED

    def disarm(self) -> None:
        """Return to idle, e.g. after an explicit stop."""
        self._last_fed_at = None
        self._status = WatchdogStatus.IDLE

    def check(self) -> bool:
        """Return True exactly once when an armed watchdog has timed out."""
        if self._status is not WatchdogStatus.ARMED or self._last_fed_at is None:
            return False
        if self._clock() - self._last_fed_at <= self._timeout_s:
            return False
        self._status = WatchdogStatus.TIMED_OUT
        return True

    def seconds_since_feed(self) -> float | None:
        """Return seconds since the last valid command, if armed or timed out."""
        if self._last_fed_at is None:
            return None
        return self._clock() - self._last_fed_at

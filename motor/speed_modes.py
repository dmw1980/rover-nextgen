"""Operator-selectable speed limits for manual driving."""

from enum import Enum


class SpeedMode(str, Enum):
    """Manual speed modes and their maximum output magnitude in percent."""

    LOW = "LOW"
    HIGH = "HIGH"

    @property
    def max_percent(self) -> float:
        """Return the maximum allowed output magnitude for this mode."""
        return _MAX_PERCENT[self]

    def limit(self, percent: float) -> float:
        """Clamp a signed percentage to this mode's output limit."""
        maximum = self.max_percent
        return max(-maximum, min(maximum, percent))


_MAX_PERCENT: dict[SpeedMode, float] = {
    SpeedMode.LOW: 40.0,
    SpeedMode.HIGH: 100.0,
}

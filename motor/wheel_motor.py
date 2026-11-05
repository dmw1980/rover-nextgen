"""Hardware-independent BTS7960 wheel motor command abstraction."""

from dataclasses import dataclass, field
from math import isfinite

from config.settings import HARDWARE, PCA9685_MOTOR_CHANNELS, WheelPosition


@dataclass(slots=True)
class WheelMotor:
    """Track one wheel's BTS7960 PWM command using configured PCA9685 channels.

    The first configured channel is used for forward output and the second for
    reverse output. This class records commands only; it does not access hardware.
    """

    position: WheelPosition
    forward_channel: int = field(init=False)
    reverse_channel: int = field(init=False)
    forward_percent: float = field(default=0.0, init=False)
    reverse_percent: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        """Load the configured PWM channels for this wheel."""
        if HARDWARE.motor_system.pwm_controller_model != "PCA9685":
            raise ValueError("WheelMotor requires a PCA9685 PWM controller.")

        driver = next(
            driver
            for driver in HARDWARE.motor_system.motor_drivers
            if driver.position is self.position
        )
        if driver.model != "BTS7960":
            raise ValueError("WheelMotor requires a BTS7960 motor driver.")

        channels = PCA9685_MOTOR_CHANNELS[self.position]
        self.forward_channel, self.reverse_channel = channels

    def set_speed(self, percent: float) -> None:
        """Set signed speed: positive is forward, negative is reverse."""
        self._validate_percent(percent, allow_negative=True)
        if percent > 0:
            self.set_forward(percent)
        elif percent < 0:
            self.set_reverse(-percent)
        else:
            self.stop()

    def set_forward(self, percent: float) -> None:
        """Set forward speed from zero through 100 percent."""
        self._validate_percent(percent)
        self.forward_percent = float(percent)
        self.reverse_percent = 0.0

    def set_reverse(self, percent: float) -> None:
        """Set reverse speed from zero through 100 percent."""
        self._validate_percent(percent)
        self.forward_percent = 0.0
        self.reverse_percent = float(percent)

    def stop(self) -> None:
        """Clear both PWM commands."""
        self.forward_percent = 0.0
        self.reverse_percent = 0.0

    @staticmethod
    def _validate_percent(percent: float, *, allow_negative: bool = False) -> None:
        """Reject non-finite or out-of-range speed commands."""
        minimum = -100.0 if allow_negative else 0.0
        if not isfinite(percent) or not minimum <= percent <= 100.0:
            raise ValueError(f"Speed must be between {minimum:g} and 100 percent.")
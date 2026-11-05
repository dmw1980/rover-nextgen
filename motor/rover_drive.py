"""Hardware-independent drive commands for a four-wheel rover."""

from dataclasses import dataclass

from motor.wheel_motor import WheelMotor


@dataclass(slots=True)
class RoverDrive:
    """Coordinate four ``WheelMotor`` objects as a differential-drive rover."""

    front_left: WheelMotor
    front_right: WheelMotor
    rear_left: WheelMotor
    rear_right: WheelMotor

    def stop(self) -> None:
        """Stop all four wheels."""
        for wheel in self._wheels:
            wheel.stop()

    def drive_forward(self, speed: float) -> None:
        """Drive all four wheels forward at the given percentage."""
        for wheel in self._wheels:
            wheel.set_forward(speed)

    def drive_reverse(self, speed: float) -> None:
        """Drive all four wheels in reverse at the given percentage."""
        for wheel in self._wheels:
            wheel.set_reverse(speed)

    def turn_left(self, speed: float) -> None:
        """Pivot left by reversing the left wheels and advancing the right."""
        self.front_left.set_reverse(speed)
        self.rear_left.set_reverse(speed)
        self.front_right.set_forward(speed)
        self.rear_right.set_forward(speed)

    def turn_right(self, speed: float) -> None:
        """Pivot right by advancing the left wheels and reversing the right."""
        self.front_left.set_forward(speed)
        self.rear_left.set_forward(speed)
        self.front_right.set_reverse(speed)
        self.rear_right.set_reverse(speed)

    def tank_drive(self, left_speed: float, right_speed: float) -> None:
        """Set signed speeds independently for the left and right wheel pairs."""
        self.front_left.set_speed(left_speed)
        self.rear_left.set_speed(left_speed)
        self.front_right.set_speed(right_speed)
        self.rear_right.set_speed(right_speed)

    @property
    def _wheels(self) -> tuple[WheelMotor, WheelMotor, WheelMotor, WheelMotor]:
        """Return the wheel objects in front-left, front-right, rear-left, rear-right order."""
        return (
            self.front_left,
            self.front_right,
            self.rear_left,
            self.rear_right,
        )

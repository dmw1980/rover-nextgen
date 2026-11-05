"""Thread-safe web control session around the hardware-independent RoverDrive."""

import logging
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from math import isfinite
from typing import Any

from config.settings import WheelPosition
from core.state import DeviceState, RoverMode, RoverState
from core.watchdog import CommandWatchdog
from motor.rover_drive import RoverDrive
from motor.speed_modes import SpeedMode
from motor.wheel_motor import WheelMotor

logger = logging.getLogger(__name__)

MAX_COMMAND_PERCENT = 100.0
CONTROL_SOURCE = "WEB"


class CommandError(ValueError):
    """Raised when a client command payload is malformed or out of range."""


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Outcome of a control command, safe to return to a Socket.IO client."""

    ok: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {"ok": self.ok, "error": self.error}


def parse_percent(value: object, name: str) -> float:
    """Validate one signed percentage; reject non-numbers, NaN, inf, and out-of-range values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CommandError(f"'{name}' must be a number.")
    if isinstance(value, float) and not isfinite(value):
        raise CommandError(f"'{name}' must be finite.")
    if abs(value) > MAX_COMMAND_PERCENT:
        raise CommandError(f"'{name}' must be between -100 and 100.")
    return float(value)


def parse_drive_payload(payload: object) -> tuple[float, float]:
    """Validate a drive payload of the form ``{"left": n, "right": n}``."""
    if not isinstance(payload, Mapping):
        raise CommandError("Drive payload must be an object.")
    if "left" not in payload or "right" not in payload:
        raise CommandError("Drive payload requires 'left' and 'right'.")
    return parse_percent(payload["left"], "left"), parse_percent(payload["right"], "right")


def parse_speed_mode_payload(payload: object) -> SpeedMode:
    """Validate a speed-mode payload of the form ``{"mode": "LOW" | "HIGH"}``."""
    if not isinstance(payload, Mapping) or "mode" not in payload:
        raise CommandError("Speed-mode payload requires 'mode'.")
    mode = payload["mode"]
    if not isinstance(mode, str) or mode not in SpeedMode.__members__:
        raise CommandError("Speed mode must be 'LOW' or 'HIGH'.")
    return SpeedMode[mode]


def build_rover_drive() -> RoverDrive:
    """Create a RoverDrive from simulation-only WheelMotor objects."""
    return RoverDrive(
        front_left=WheelMotor(WheelPosition.FL),
        front_right=WheelMotor(WheelPosition.FR),
        rear_left=WheelMotor(WheelPosition.RL),
        rear_right=WheelMotor(WheelPosition.RR),
    )


def _signed_percent(wheel: WheelMotor) -> float:
    """Return a wheel's commanded output: positive forward, negative reverse."""
    return wheel.forward_percent - wheel.reverse_percent


def _device_to_dict(device: DeviceState) -> dict[str, Any]:
    """Serialize a device status snapshot."""
    return {
        "id": device.device_id,
        "status": device.status.value,
        "error": device.error_message,
    }


class WebRoverController:
    """Own the shared RoverDrive and web-control session state.

    RoverState is immutable, so mode changes produce replacement snapshots.
    Everything else (speed mode, emergency stop, clients, watchdog) lives here.
    All safety defaults apply: stopped, LOW speed, emergency stop clear.
    """

    def __init__(
        self,
        drive: RoverDrive | None = None,
        watchdog_timeout_s: float = 0.5,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._lock = threading.RLock()
        self._drive = drive if drive is not None else build_rover_drive()
        self._watchdog = CommandWatchdog(timeout_s=watchdog_timeout_s, clock=clock)
        self._base_state = RoverState()
        self._speed_mode = SpeedMode.LOW
        self._emergency_stop = False
        self._clients = 0

    @property
    def drive(self) -> RoverDrive:
        """Return the shared RoverDrive."""
        return self._drive

    @property
    def speed_mode(self) -> SpeedMode:
        """Return the active speed mode."""
        with self._lock:
            return self._speed_mode

    @property
    def emergency_stop_active(self) -> bool:
        """Return whether the emergency stop is latched."""
        with self._lock:
            return self._emergency_stop

    def drive_command(self, payload: object) -> CommandResult:
        """Validate and apply a tank-drive command.

        Invalid payloads and drive requests during emergency stop leave the
        rover stopped. Valid values are limited by the active speed mode.
        """
        with self._lock:
            try:
                left, right = parse_drive_payload(payload)
            except CommandError as error:
                self._stop_locked()
                return CommandResult(False, str(error))
            if self._emergency_stop:
                self._stop_locked()
                return CommandResult(False, "Emergency stop is active.")
            self._drive.tank_drive(self._speed_mode.limit(left), self._speed_mode.limit(right))
            self._watchdog.feed()
            return CommandResult(True)

    def stop(self) -> CommandResult:
        """Stop all wheels."""
        with self._lock:
            self._stop_locked()
            return CommandResult(True)

    def emergency_stop(self) -> CommandResult:
        """Latch the emergency stop and stop all wheels."""
        with self._lock:
            self._emergency_stop = True
            self._stop_locked()
            return CommandResult(True)

    def clear_emergency_stop(self) -> CommandResult:
        """Release the emergency stop without resuming any movement."""
        with self._lock:
            self._emergency_stop = False
            self._stop_locked()
            return CommandResult(True)

    def set_speed_mode(self, payload: object) -> CommandResult:
        """Change the speed mode and stop so the new limit needs a fresh command."""
        with self._lock:
            try:
                mode = parse_speed_mode_payload(payload)
            except CommandError as error:
                return CommandResult(False, str(error))
            self._speed_mode = mode
            self._stop_locked()
            return CommandResult(True)

    def client_connected(self) -> None:
        """Register a connected browser client."""
        with self._lock:
            self._clients += 1

    def client_disconnected(self) -> None:
        """Unregister a browser client and stop immediately."""
        with self._lock:
            self._clients = max(0, self._clients - 1)
            self._stop_locked()

    def check_watchdog(self) -> bool:
        """Stop the rover if the command watchdog expired; return True when it did."""
        with self._lock:
            if not self._watchdog.check():
                return False
            self._drive.stop()
            logger.warning("Command watchdog timed out; rover stopped.")
            return True

    def safe_stop(self) -> bool:
        """Best-effort stop for error and shutdown paths; return whether it succeeded."""
        try:
            with self._lock:
                self._stop_locked()
        except Exception:
            logger.exception("Failed to stop the rover.")
            return False
        return True

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable telemetry snapshot."""
        with self._lock:
            drive = self._drive
            wheel_objects = (
                drive.front_left,
                drive.front_right,
                drive.rear_left,
                drive.rear_right,
            )
            wheels = {wheel.position.value: _signed_percent(wheel) for wheel in wheel_objects}
            state = self._current_state()
            age = self._watchdog.seconds_since_feed()
            return {
                "control_source": CONTROL_SOURCE,
                "simulation": True,
                "rover_mode": state.mode.value,
                "speed_mode": self._speed_mode.value,
                "speed_limit_percent": self._speed_mode.max_percent,
                "emergency_stop": self._emergency_stop,
                "connected_clients": self._clients,
                "command": {
                    "left": _signed_percent(drive.front_left),
                    "right": _signed_percent(drive.front_right),
                },
                "wheels": wheels,
                "watchdog": {
                    "status": self._watchdog.status.value,
                    "timeout_ms": round(self._watchdog.timeout_s * 1000),
                    "last_command_age_ms": None if age is None else round(age * 1000),
                },
                "battery": {
                    "status": state.battery.status.value,
                    "voltage_v": state.battery.voltage_v,
                    "current_a": state.battery.current_a,
                    "charge_percent": state.battery.charge_percent,
                },
                "imu": _device_to_dict(state.imu),
                "lidar": _device_to_dict(state.lidar),
                "cameras": {camera.device_id: _device_to_dict(camera) for camera in state.cameras},
            }

    def _current_state(self) -> RoverState:
        """Return a replacement RoverState reflecting the current control mode."""
        if self._emergency_stop:
            mode = RoverMode.EMERGENCY_STOP
        elif self._clients > 0:
            mode = RoverMode.MANUAL
        else:
            mode = RoverMode.DISARMED
        self._base_state = replace(self._base_state, mode=mode)
        return self._base_state

    def _stop_locked(self) -> None:
        """Stop all wheels and disarm the watchdog; caller holds the lock."""
        self._drive.stop()
        self._watchdog.disarm()

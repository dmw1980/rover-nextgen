"""Immutable data models for the rover's runtime state."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from config.settings import WheelPosition


class RoverMode(str, Enum):
    """Current rover operating mode."""

    DISARMED = "disarmed"
    MANUAL = "manual"
    AUTONOMOUS = "autonomous"
    EMERGENCY_STOP = "emergency_stop"


class DeviceStatus(str, Enum):
    """Health state reported for a device or subsystem."""

    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    READY = "ready"
    DEGRADED = "degraded"
    FAULT = "fault"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True, slots=True)
class DeviceState:
    """Status snapshot for a named device."""

    device_id: str
    status: DeviceStatus = DeviceStatus.NOT_INITIALIZED
    last_seen_at: datetime | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class BatteryState:
    """Available battery telemetry and monitoring status."""

    status: DeviceStatus = DeviceStatus.NOT_INITIALIZED
    voltage_v: float | None = None
    current_a: float | None = None
    charge_percent: float | None = None


@dataclass(frozen=True, slots=True)
class WheelState:
    """Command, telemetry, and device status for one wheel."""

    position: WheelPosition
    target_speed_mps: float = 0.0
    measured_speed_mps: float | None = None
    odometry_ticks: int = 0
    motor_status: DeviceStatus = DeviceStatus.NOT_INITIALIZED
    odometry_status: DeviceStatus = DeviceStatus.NOT_INITIALIZED


@dataclass(frozen=True, slots=True)
class RoverState:
    """Immutable snapshot of rover mode, battery, wheels, and device health."""

    mode: RoverMode = RoverMode.DISARMED
    battery: BatteryState = field(default_factory=BatteryState)
    wheels: tuple[WheelState, ...] = (
        WheelState(WheelPosition.FL),
        WheelState(WheelPosition.FR),
        WheelState(WheelPosition.RL),
        WheelState(WheelPosition.RR),
    )
    imu: DeviceState = field(default_factory=lambda: DeviceState("bno085_imu"))
    lidar: DeviceState = field(default_factory=lambda: DeviceState("rplidar_c1"))
    cameras: tuple[DeviceState, ...] = (
        DeviceState("front_camera"),
        DeviceState("rear_camera"),
    )
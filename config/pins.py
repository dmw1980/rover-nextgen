"""Logical hardware signal names; no physical pins or channels are assigned."""

from dataclasses import dataclass

from config.settings import WheelPosition


@dataclass(frozen=True, slots=True)
class WheelSignalNames:
    """Logical motor and odometry signals associated with one wheel."""

    position: WheelPosition
    motor: str
    odometry: str


@dataclass(frozen=True, slots=True)
class HardwareSignalNames:
    """Logical names for the rover's documented signal-producing devices."""

    wheels: tuple[WheelSignalNames, ...]
    bno085: str
    rplidar_c1: str
    ads1115: str
    bme280: str
    vl53l1x_sensors: tuple[str, ...]


# The VL53L1X names identify sensors only; their physical positions are unspecified.
SIGNALS = HardwareSignalNames(
    wheels=(
        WheelSignalNames(WheelPosition.FL, "motor.fl", "odometry.fl"),
        WheelSignalNames(WheelPosition.FR, "motor.fr", "odometry.fr"),
        WheelSignalNames(WheelPosition.RL, "motor.rl", "odometry.rl"),
        WheelSignalNames(WheelPosition.RR, "motor.rr", "odometry.rr"),
    ),
    bno085="imu.bno085",
    rplidar_c1="lidar.rplidar_c1",
    ads1115="adc.ads1115",
    bme280="environment.bme280",
    vl53l1x_sensors=(
        "tof.vl53l1x_a",
        "tof.vl53l1x_b",
        "tof.vl53l1x_c",
        "tof.vl53l1x_d",
    ),
)
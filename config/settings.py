"""Typed inventory of the rover's documented hardware."""

from dataclasses import dataclass
from enum import Enum


class WheelPosition(str, Enum):
    """Canonical positions for independently controlled rover wheels."""

    FL = "FL"
    FR = "FR"
    RL = "RL"
    RR = "RR"


class CameraPosition(str, Enum):
    """Mounting positions of the rover's cameras."""

    FRONT = "front"
    REAR = "rear"


@dataclass(frozen=True, slots=True)
class SensorHardware:
    """Model and documented quantity for a sensor type."""

    model: str
    quantity: int = 1

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Sensor model must not be empty.")
        if self.quantity < 1:
            raise ValueError("Sensor quantity must be at least one.")


@dataclass(frozen=True, slots=True)
class WheelOdometrySensor:
    """SN04-N sensor associated with one physical wheel."""

    position: WheelPosition
    model: str = "SN04-N"


@dataclass(frozen=True, slots=True)
class SensorInventory:
    """Installed navigation, ranging, and environment sensors."""

    imu: SensorHardware
    lidar: SensorHardware
    analog_to_digital_converter: SensorHardware
    environmental: SensorHardware
    time_of_flight: SensorHardware
    wheel_odometry: tuple[WheelOdometrySensor, ...]

    def __post_init__(self) -> None:
        positions = tuple(sensor.position for sensor in self.wheel_odometry)
        if len(positions) != len(WheelPosition) or set(positions) != set(WheelPosition):
            raise ValueError("Odometry inventory must contain one sensor per wheel.")


@dataclass(frozen=True, slots=True)
class MotorDriverHardware:
    """BTS7960 motor driver dedicated to one independently controlled wheel."""

    position: WheelPosition
    model: str = "BTS7960"


@dataclass(frozen=True, slots=True)
class MotorSystem:
    """Four individually driven wheels and their PWM controller."""

    motor_drivers: tuple[MotorDriverHardware, ...]
    pwm_controller_model: str

    def __post_init__(self) -> None:
        positions = tuple(driver.position for driver in self.motor_drivers)
        if len(positions) != len(WheelPosition) or set(positions) != set(WheelPosition):
            raise ValueError("Motor system must contain one driver per wheel.")
        if not self.pwm_controller_model.strip():
            raise ValueError("PWM controller model must not be empty.")


@dataclass(frozen=True, slots=True)
class CameraHardware:
    """USB webcam and its documented mounting position."""

    position: CameraPosition
    model: str = "Trust Trino HD"
    interface: str = "USB"
    resolution: tuple[int, int] = (1280, 720)

    def __post_init__(self) -> None:
        if not self.model.strip() or not self.interface.strip():
            raise ValueError("Camera model and interface must not be empty.")
        if len(self.resolution) != 2 or any(dimension < 1 for dimension in self.resolution):
            raise ValueError("Camera resolution must contain positive width and height.")


@dataclass(frozen=True, slots=True)
class ControllerHardware:
    """Documented operator controller and its onboard controls."""

    model: str
    connection: str
    has_six_axis_imu: bool
    has_touchpad: bool


@dataclass(frozen=True, slots=True)
class SwitchedOutputHardware:
    """MOSFET modules and logical lighting outputs; no pin mapping is implied."""

    mosfet_module_model: str
    quantity: int
    front_rgbw_outputs: tuple[str, ...]
    rear_rgbw_outputs: tuple[str, ...]
    reserved_outputs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.mosfet_module_model.strip():
            raise ValueError("MOSFET module model must not be empty.")
        if self.quantity != 10:
            raise ValueError("Lighting inventory must contain ten MOSFET modules.")
        if len(self.front_rgbw_outputs) != 4 or len(self.rear_rgbw_outputs) != 4:
            raise ValueError("Front and rear lighting must each define four RGBW outputs.")
        if len(self.reserved_outputs) != 2:
            raise ValueError("Lighting inventory must define two reserved outputs.")
        outputs = self.front_rgbw_outputs + self.rear_rgbw_outputs + self.reserved_outputs
        if len(set(outputs)) != self.quantity:
            raise ValueError("Each MOSFET module must have one unique logical output.")


@dataclass(frozen=True, slots=True)
class RoverHardware:
    """Complete documented hardware inventory; no pin assignments are implied."""

    compute_board_model: str
    motor_system: MotorSystem
    sensors: SensorInventory
    cameras: tuple[CameraHardware, ...]
    controller: ControllerHardware
    switched_outputs: SwitchedOutputHardware

    def __post_init__(self) -> None:
        if not self.compute_board_model.strip():
            raise ValueError("Compute board model must not be empty.")
        camera_positions = tuple(camera.position for camera in self.cameras)
        if len(camera_positions) != len(CameraPosition) or set(camera_positions) != set(CameraPosition):
            raise ValueError("Camera inventory must contain front and rear cameras.")
        driver_positions = {driver.position for driver in self.motor_system.motor_drivers}
        odometry_positions = {sensor.position for sensor in self.sensors.wheel_odometry}
        if driver_positions != odometry_positions:
            raise ValueError("Each wheel driver must correspond to a wheel odometry sensor.")


HARDWARE = RoverHardware(
    compute_board_model="Raspberry Pi 4B",
    motor_system=MotorSystem(
        motor_drivers=(
            MotorDriverHardware(WheelPosition.FL),
            MotorDriverHardware(WheelPosition.FR),
            MotorDriverHardware(WheelPosition.RL),
            MotorDriverHardware(WheelPosition.RR),
        ),
        pwm_controller_model="PCA9685",
    ),
    sensors=SensorInventory(
        imu=SensorHardware(model="BNO085 9DOF IMU"),
        lidar=SensorHardware(model="Slamtec RPLIDAR C1"),
        analog_to_digital_converter=SensorHardware(model="ADS1115"),
        environmental=SensorHardware(model="BME280"),
        time_of_flight=SensorHardware(model="VL53L1X", quantity=4),
        wheel_odometry=(
            WheelOdometrySensor(WheelPosition.FL),
            WheelOdometrySensor(WheelPosition.FR),
            WheelOdometrySensor(WheelPosition.RL),
            WheelOdometrySensor(WheelPosition.RR),
        ),
    ),
    cameras=(
        CameraHardware(CameraPosition.FRONT),
        CameraHardware(CameraPosition.REAR),
    ),
    controller=ControllerHardware(
        model="LATEC PS4 Controller",
        connection="Bluetooth",
        has_six_axis_imu=True,
        has_touchpad=True,
    ),
    switched_outputs=SwitchedOutputHardware(
        mosfet_module_model="IRLZ44N",
        quantity=10,
        front_rgbw_outputs=("FRONT_R", "FRONT_G", "FRONT_B", "FRONT_W"),
        rear_rgbw_outputs=("REAR_R", "REAR_G", "REAR_B", "REAR_W"),
        reserved_outputs=("AUX_1", "AUX_2"),
    ),
)
from pathlib import Path

folders = [
    "config",
    "core",
    "motor",
    "gamepad",
    "io",
    "video",

    "sensors/imu",
    "sensors/battery",
    "sensors/encoders",
    "sensors/inductive",
    "sensors/lidar",

    "navigation/localization",
    "navigation/mapping",
    "navigation/obstacle_avoidance",
    "navigation/planner",
    "navigation/autonomous",

    "web/static/css",
    "web/static/js",
    "web/static/images",
    "web/templates",

    "tests",
    "docs"
]

files = [
    "start.py",
    "requirements.txt",
    "README.md",

    "config/settings.py",
    "config/pins.py",

    "core/state.py",
    "core/watchdog.py",
    "core/logger.py",

    "motor/motor_controller.py",
    "motor/mixer.py",
    "motor/speed_modes.py",

    "gamepad/controller.py",
    "gamepad/gamepad_imu.py",
    "gamepad/mappings.py",

    "io/i2c_expander.py",

    "video/camera.py",
    "video/streamer.py",
    "video/recorder.py",

    "sensors/imu/rover_imu.py",
    "sensors/battery/battery_monitor.py",
    "sensors/encoders/wheel_encoder.py",
    "sensors/inductive/inductive_sensors.py",
    "sensors/lidar/lidar.py",

    "navigation/localization/pose_estimator.py",
    "navigation/localization/sensor_fusion.py",

    "navigation/mapping/occupancy_grid.py",

    "navigation/obstacle_avoidance/avoidance.py",

    "navigation/planner/path_planner.py",

    "navigation/autonomous/autonomous_controller.py",

    "web/app.py",
    "web/routes.py",
    "web/socketio_events.py",
    "web/templates/index.html",

    "docs/architecture.md",
    "docs/pinout.md",
    "docs/wiring.md",
    "docs/imu.md",
    "docs/lidar.md",
    "docs/battery.md",

    "tests/test_motor.py",
    "tests/test_camera.py",
    "tests/test_imu.py",
    "tests/test_lidar.py"
]

for folder in folders:
    Path(folder).mkdir(parents=True, exist_ok=True)

for file in files:
    path = Path(file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)

print("Rover NextGen Struktur erstellt")

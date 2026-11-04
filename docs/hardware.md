# Rover Hardware Inventory

This document records the rover's current hardware by subsystem. Pin
assignments and wiring are documented separately.

## Compute

| Qty. | Component | Model / details | Role |
|---:|---|---|---|
| 1 | Single-board computer | Raspberry Pi 4B | Rover compute platform |

## Drive and wheel odometry

The rover uses individual wheel control, with one BTS7960 motor driver and one
SN04-N wheel odometry sensor assigned to each wheel.

| Wheel | Position | Motor driver | Odometry sensor |
|---|---|---|---|
| FL | Front left | BTS7960 | SN04-N |
| FR | Front right | BTS7960 | SN04-N |
| RL | Rear left | BTS7960 | SN04-N |
| RR | Rear right | BTS7960 | SN04-N |

## Navigation and ranging

| Qty. | Component | Model / details | Role |
|---:|---|---|---|
| 1 | 9-DOF IMU | BNO085 | Rover orientation and motion sensing |
| 1 | LiDAR | Slamtec RPLIDAR C1 | Ranging for mapping and obstacle detection |
| 4 | Time-of-flight distance sensors | VL53L1X | Short-range distance sensing |

## Environmental and analog sensing

| Qty. | Component | Model / details | Role |
|---:|---|---|---|
| 1 | Environmental sensor | BME280; temperature, humidity, and pressure | Environmental measurements |
| 1 | Analog-to-digital converter | ADS1115; 16-bit, 4-channel | Reading analog sensor signals |

## Video

| Qty. | Component | Model / details | Role |
|---:|---|---|---|
| 2 | USB webcam | Trust Trino HD; 1280 × 720 | Front and rear video capture |

## Operator input and control

| Qty. | Component | Model / details | Role |
|---:|---|---|---|
| 1 | Game controller | LATEC PS4 Controller; Bluetooth, 6-axis IMU, and touchpad | Manual rover control |
| 1 | PWM controller | PCA9685 | PWM signal generation |

## Switched outputs

| Qty. | Component | Model / details | Role |
|---:|---|---|---|
| 10 | MOSFET modules | IRLZ44N | Front/rear RGBW lighting and reserved auxiliary outputs |

### Lighting outputs

| Group | Logical outputs |
|---|---|
| Front RGBW | `FRONT_R`, `FRONT_G`, `FRONT_B`, `FRONT_W` |
| Rear RGBW | `REAR_R`, `REAR_G`, `REAR_B`, `REAR_W` |
| Reserved | `AUX_1`, `AUX_2` (no physical assignment yet) |

These are logical inventory names only. No GPIO mappings or PCA9685 channel
assignments are specified here.

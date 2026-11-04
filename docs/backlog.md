# Rover Development Roadmap

This roadmap sequences implementation around the hardware listed in
[hardware.md](./hardware.md). It describes development work only; it does not
assign GPIO pins, PCA9685 channels, or wiring.

## Phase 1 — Configuration

- Define typed configuration for the Raspberry Pi 4B, four wheel positions
  (FL, FR, RL, RR), and the installed sensor, camera, controller, motor-driver,
  PWM-controller, and switched-output inventory.
- Keep electrical assignments separate from hardware identity; document GPIO,
  I2C, USB, and PCA9685 channel mappings only after wiring is finalized.
- Validate required component counts and unique wheel/camera assignments.

**Completion:** The documented inventory can be represented and validated
without opening hardware devices.

## Phase 2 — State management

- Define immutable rover-mode, wheel, battery, sensor, and device-health state
  models.
- Include independent state for each wheel, its BTS7960 driver, and its SN04-N
  odometry sensor.
- Represent health for the BNO085, RPLIDAR C1, both Trust Trino HD cameras, and
  other inventoried devices.

**Completion:** State can be created, updated through replacement snapshots,
and tested without hardware access.

## Phase 3 — Wheel odometry (SN04-N)

- Implement one odometry input per wheel: FL, FR, RL, and RR.
- Establish and document signal conditioning, safe Pi input levels, and the
  finalized GPIO mapping before connecting sensors.
- Track wheel pulse counts and derive wheel motion using measured wheel
  parameters.
- Test direction/rotation interpretation, missing pulses, and sensor faults.

**Completion:** Each wheel produces independently verifiable odometry data.

## Phase 4 — BNO085

- Integrate the BNO085 and expose timestamped orientation and motion readings.
- Define calibration, startup, stale-data, and sensor-fault behavior.
- Validate orientation and motion output while the rover is stationary and
  during controlled movement.

**Completion:** IMU readings are available to state and navigation components
with health and freshness information.

## Phase 5 — BTS7960 wheel control

- Implement four independent motor outputs, pairing one BTS7960 with each
  wheel: FL, FR, RL, and RR.
- Configure the PCA9685 only after its wiring and channel allocation have been
  documented and verified.
- Define direction, speed-command limits, startup defaults, and a safe stop
  response for faults or loss of control.
- Test each wheel independently with wheels raised before floor testing.

**Completion:** Each wheel can be commanded and stopped independently with
verified safe behavior.

## Phase 6 — Camera subsystem

- Discover and identify both Trust Trino HD USB cameras as front and rear
  views.
- Provide independent capture, resource cleanup, and camera-health reporting.
- Validate expected 1280 × 720 capture and behavior when a camera disconnects.

**Completion:** Both camera streams can be used independently and failures are
reported.

## Phase 7 — RPLIDAR C1

- Integrate the Slamtec RPLIDAR C1 and publish timestamped range scans.
- Handle startup, scan validity, stale data, disconnects, and shutdown.
- Validate scan orientation and obstacle distances in a controlled test area.

**Completion:** Navigation receives valid scans with explicit sensor health.

## Phase 8 — Manual drive

- Integrate the LATEC PS4 Controller over Bluetooth, including connection loss
  and controller-health reporting.
- Map manual inputs to four-wheel commands while preserving independent wheel
  control.
- Apply command limits, dead zones, and an operator emergency-stop path.
- Verify stop behavior when input is released or the controller disconnects.

**Completion:** An operator can drive, stop, and recover safely in a controlled
test environment.

## Phase 9 — Autonomous navigation

- Combine wheel odometry, BNO085 orientation, and RPLIDAR C1 scans for
  localization and obstacle awareness.
- Build and validate mapping, path planning, and obstacle-avoidance behaviors.
- Define safety constraints, manual override, and behavior on stale or failed
  sensors.
- Test incrementally in a bounded area before expanding the operating space.

**Completion:** The rover can follow a bounded autonomous route and stop safely
when its navigation inputs or safety conditions are invalid.

## Phase 10 — Return home

- Define and persist a home pose or safe return location.
- Plan a route home using the validated localization, mapping, and navigation
  capabilities from earlier phases.
- Handle blocked routes, localization loss, low battery, and manual takeover.
- Test return-to-home behavior in a controlled area before relying on it
  unattended.

**Completion:** The rover can attempt a safe return to its configured home
location and report when it cannot complete the return.

## Lighting System

The lighting system is documented as logical outputs and rover status states.
The patterns below specify visual behavior only. GPIO pins, PCA9685 channels,
and wiring are not assigned here.

### Logical outputs

| Group | Logical signals | Purpose |
|---|---|---|
| Front RGBW | `FRONT_R`, `FRONT_G`, `FRONT_B`, `FRONT_W` | Red, green, blue, and white front lighting channels |
| Rear RGBW | `REAR_R`, `REAR_G`, `REAR_B`, `REAR_W` | Red, green, blue, and white rear lighting channels |
| Reserved | `AUX_1`, `AUX_2` | Reserved; no physical assignment yet |

### Lighting patterns

| State | Front | Rear | Additional details |
|---|---|---|---|
| `Boot` | Blue, slow pulse | Blue, slow pulse | |
| `Ready` | White at 50% | White at 20% | |
| `Manual` | White at 100% | Red at 30% | |
| `Autonomous` | White at 70% with green status indication | Green at 60% | |
| `Return Home` | White at 70% | Cyan, slow pulse | |
| `Obstacle Warning` | Yellow, blinking | Yellow, blinking | Blink frequency: 2 Hz |
| `Low Battery` | Orange at 50% | Orange at 50% | Suggested threshold: 20% |
| `Critical Battery` | Red, blinking | Red, blinking | Blink frequency: 2 Hz; suggested threshold: 10% |
| `Charging` | Blue, slow pulse | Blue, slow pulse | |
| `WiFi Lost` | Magenta, blinking | Magenta, blinking | Blink frequency: 1 Hz |
| `Sensor Fault` | Alternate red and yellow | Alternate red and yellow | Pattern frequency: 1 Hz |
| `Emergency Stop` | Solid red at 100% | Solid red at 100% | Highest priority; overrides every other lighting state |

### State priority

When multiple lighting states apply, use this priority order from highest to
lowest:

1. `Emergency Stop`
2. `Critical Battery`
3. `Sensor Fault`
4. `WiFi Lost`
5. `Obstacle Warning`
6. `Return Home`
7. `Charging`
8. `Low Battery`
9. `Autonomous`
10. `Manual`
11. `Ready`
12. `Boot`

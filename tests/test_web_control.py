"""Tests for the simulation-only web control interface."""

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from web.app import WebConfig, WebServices, create_app
from web.control import CommandError, parse_drive_payload

REPO_ROOT = Path(__file__).resolve().parents[1]
APP_JS = REPO_ROOT / "web" / "static" / "js" / "app.js"
FORBIDDEN_MODULES = ("RPi", "gpiozero", "pigpio", "board", "busio", "adafruit_pca9685", "smbus2", "cv2", "serial")


class FakeClock:
    """Manually advanced monotonic clock."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def app(clock: FakeClock):
    config = WebConfig(watchdog_timeout_ms=500, start_watchdog_monitor=False)
    application = create_app(config, clock=clock)
    yield application
    application.extensions["rover_web"].shutdown()


@pytest.fixture
def services(app) -> WebServices:
    return app.extensions["rover_web"]


@pytest.fixture
def client(app, services):
    sio_client = services.socketio.test_client(app)
    yield sio_client
    if sio_client.is_connected():
        sio_client.disconnect()


def get_state(app) -> dict[str, Any]:
    response = app.test_client().get("/api/state")
    assert response.status_code == 200
    return response.get_json()


def drive(client, payload: Any) -> dict[str, Any]:
    return client.emit("drive", payload, callback=True)


def assert_stopped(state: dict[str, Any]) -> None:
    assert state["command"] == {"left": 0.0, "right": 0.0}
    assert all(value == 0.0 for value in state["wheels"].values())


def test_health_endpoint(app) -> None:
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "healthy"
    assert body["simulation"] is True


def test_initial_state_is_stopped_low_and_safe(app) -> None:
    state = get_state(app)
    assert_stopped(state)
    assert set(state["wheels"]) == {"FL", "FR", "RL", "RR"}
    assert state["speed_mode"] == "LOW"
    assert state["speed_limit_percent"] == 40.0
    assert state["emergency_stop"] is False
    assert state["control_source"] == "WEB"
    assert state["rover_mode"] == "disarmed"
    assert state["watchdog"]["status"] == "idle"
    assert state["watchdog"]["timeout_ms"] == 500
    json.dumps(state)


def test_index_page_is_served_without_external_assets(app) -> None:
    response = app.test_client().get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "XMW Rover NextGen" in html
    assert "http://" not in html and "https://" not in html
    assert app.test_client().get("/static/js/app.js").status_code == 200
    assert app.test_client().get("/static/css/style.css").status_code == 200
    assert app.test_client().get("/static/js/vendor/socket.io.min.js").status_code == 200


def test_valid_tank_drive_command(app, client) -> None:
    assert drive(client, {"left": 30, "right": -20}) == {"ok": True, "error": None}
    state = get_state(app)
    assert state["command"] == {"left": 30.0, "right": -20.0}
    assert state["wheels"] == {"FL": 30.0, "RL": 30.0, "FR": -20.0, "RR": -20.0}
    assert state["watchdog"]["status"] == "armed"
    assert state["rover_mode"] == "manual"


def test_state_is_broadcast_after_drive(client) -> None:
    client.get_received()
    drive(client, {"left": 10, "right": 10})
    events = [event for event in client.get_received() if event["name"] == "state"]
    assert events
    assert events[-1]["args"][0]["command"] == {"left": 10.0, "right": 10.0}


@pytest.mark.parametrize(
    "payload",
    [
        None,
        "left",
        42,
        [],
        {},
        {"left": 10},
        {"right": 10},
        {"left": "10", "right": 0},
        {"left": None, "right": 0},
        {"left": 0, "right": None},
        {"left": True, "right": 0},
        {"left": [1], "right": 0},
        {"left": float("nan"), "right": 0},
        {"left": 0, "right": float("inf")},
        {"left": 0, "right": float("-inf")},
        {"left": 100.5, "right": 0},
        {"left": 0, "right": -101},
        {"left": 10**50, "right": 0},
    ],
)
def test_invalid_drive_payload_stops_rover(app, client, payload: Any) -> None:
    assert drive(client, {"left": 30, "right": 30})["ok"] is True
    result = drive(client, payload)
    assert result["ok"] is False
    assert result["error"]
    assert_stopped(get_state(app))


@pytest.mark.parametrize(
    "payload",
    [{"left": float("nan"), "right": 0}, {"left": "1", "right": 0}, {"left": 0}, None, {"left": 10**400, "right": 0}],
)
def test_parse_drive_payload_rejects_bad_values(payload: Any) -> None:
    with pytest.raises(CommandError):
        parse_drive_payload(payload)


def test_low_mode_limits_output_to_forty_percent(app, client) -> None:
    assert get_state(app)["speed_mode"] == "LOW"
    drive(client, {"left": 100, "right": -100})
    state = get_state(app)
    assert state["command"] == {"left": 40.0, "right": -40.0}
    assert state["wheels"]["RR"] == -40.0
    drive(client, {"left": 25, "right": 60})
    assert get_state(app)["command"] == {"left": 25.0, "right": 40.0}


def test_high_mode_allows_full_output(app, client) -> None:
    assert client.emit("set_speed_mode", {"mode": "HIGH"}, callback=True)["ok"] is True
    state = get_state(app)
    assert state["speed_mode"] == "HIGH"
    assert state["speed_limit_percent"] == 100.0
    drive(client, {"left": 100, "right": -75})
    assert get_state(app)["command"] == {"left": 100.0, "right": -75.0}


def test_speed_mode_change_stops_and_invalid_mode_is_rejected(app, client) -> None:
    drive(client, {"left": 30, "right": 30})
    assert client.emit("set_speed_mode", {"mode": "TURBO"}, callback=True)["ok"] is False
    assert get_state(app)["speed_mode"] == "LOW"
    assert client.emit("set_speed_mode", {"mode": "HIGH"}, callback=True)["ok"] is True
    assert_stopped(get_state(app))


def test_stop_event_stops_rover(app, client) -> None:
    drive(client, {"left": 30, "right": 30})
    assert client.emit("stop", callback=True)["ok"] is True
    state = get_state(app)
    assert_stopped(state)
    assert state["watchdog"]["status"] == "idle"


def test_emergency_stop_blocks_drive(app, client) -> None:
    drive(client, {"left": 30, "right": 30})
    assert client.emit("emergency_stop", callback=True)["ok"] is True
    assert_stopped(get_state(app))
    result = drive(client, {"left": 40, "right": 40})
    assert result["ok"] is False
    state = get_state(app)
    assert_stopped(state)
    assert state["emergency_stop"] is True
    assert state["rover_mode"] == "emergency_stop"


def test_clearing_emergency_stop_does_not_resume_movement(app, client) -> None:
    drive(client, {"left": 50, "right": 50})
    client.emit("emergency_stop")
    assert client.emit("clear_emergency_stop", callback=True)["ok"] is True
    state = get_state(app)
    assert state["emergency_stop"] is False
    assert_stopped(state)
    assert state["watchdog"]["status"] == "idle"
    assert drive(client, {"left": 20, "right": 20})["ok"] is True
    assert get_state(app)["command"] == {"left": 20.0, "right": 20.0}


def test_disconnect_stops_rover(app, services, client) -> None:
    drive(client, {"left": 30, "right": 30})
    assert get_state(app)["command"]["left"] == 30.0
    client.disconnect()
    state = get_state(app)
    assert_stopped(state)
    assert state["connected_clients"] == 0
    assert state["rover_mode"] == "disarmed"


def test_watchdog_stops_rover_after_timeout(app, services, client, clock: FakeClock) -> None:
    drive(client, {"left": 30, "right": 30})
    clock.advance(0.4)
    assert services.controller.check_watchdog() is False
    assert get_state(app)["command"]["left"] == 30.0

    drive(client, {"left": 30, "right": 30})  # refreshes the watchdog
    clock.advance(0.4)
    assert services.controller.check_watchdog() is False

    clock.advance(0.2)
    assert services.controller.check_watchdog() is True
    state = get_state(app)
    assert_stopped(state)
    assert state["watchdog"]["status"] == "timed_out"
    assert services.controller.check_watchdog() is False


def test_watchdog_monitor_stops_rover_in_background() -> None:
    config = WebConfig(watchdog_timeout_ms=100, start_watchdog_monitor=True)
    app = create_app(config)
    services: WebServices = app.extensions["rover_web"]
    sio_client = services.socketio.test_client(app)
    try:
        drive(sio_client, {"left": 30, "right": 30})
        assert get_state(app)["command"]["left"] == 30.0
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline and get_state(app)["watchdog"]["status"] != "timed_out":
            time.sleep(0.02)
        state = get_state(app)
        assert state["watchdog"]["status"] == "timed_out"
        assert_stopped(state)
        received = [e for e in sio_client.get_received() if e["name"] == "state"]
        assert received[-1]["args"][0]["watchdog"]["status"] == "timed_out"
    finally:
        sio_client.disconnect()
        services.shutdown()


def test_unhandled_control_error_stops_rover(app, services, client, monkeypatch) -> None:
    drive(client, {"left": 30, "right": 30})

    def explode(payload: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(services.controller, "drive_command", explode)
    result = drive(client, {"left": 30, "right": 30})
    assert result["ok"] is False
    assert_stopped(get_state(app))


def test_request_state_returns_state_event(client) -> None:
    client.get_received()
    assert client.emit("request_state", callback=True)["ok"] is True
    names = [event["name"] for event in client.get_received()]
    assert "state" in names


def test_web_modules_do_not_import_hardware_libraries() -> None:
    import web.app  # noqa: F401
    import web.control  # noqa: F401
    import web.routes  # noqa: F401
    import web.socketio_events  # noqa: F401

    loaded = [name for name in FORBIDDEN_MODULES if name in sys.modules]
    assert loaded == []


def run_node(expression: str) -> Any:
    script = f"const m = require({json.dumps(str(APP_JS))}); console.log(JSON.stringify({expression}));"
    completed = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True, timeout=20
    )
    return json.loads(completed.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
@pytest.mark.parametrize(
    ("x", "y", "left", "right"),
    [
        (0, 0, 0, 0),
        (0, -1, 100, 100),
        (0, 1, -100, -100),
        (1, 0, 100, -100),
        (-1, 0, -100, 100),
        (0.5, -0.5, 100, 0),
        (0.25, -0.5, 75, 25),
        (-0.25, -0.5, 25, 75),
        (0.7, -0.7, 100, 0),
        (5, -5, 100, 0),
    ],
)
def test_joystick_mixing(x: float, y: float, left: float, right: float) -> None:
    mixed = run_node(f"m.mixJoystick({x}, {y})")
    assert mixed["left"] == pytest.approx(left)
    assert mixed["right"] == pytest.approx(right)


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_joystick_mixing_ignores_non_finite_input_and_scales_to_limit() -> None:
    assert run_node("m.mixJoystick(NaN, Infinity)") == {"left": 0, "right": 0}
    scaled = run_node("m.scaleToLimit({left: 100, right: -50}, 40)")
    assert scaled["left"] == pytest.approx(40)
    assert scaled["right"] == pytest.approx(-20)

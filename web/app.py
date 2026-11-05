"""Flask application factory for the rover web interface."""

import logging
import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from flask import Flask
from flask_socketio import SocketIO

from web.control import WebRoverController
from web.routes import register_routes
from web.socketio_events import broadcast_state, register_socketio_events

logger = logging.getLogger(__name__)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5000
DEFAULT_WATCHDOG_TIMEOUT_MS = 500
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


@dataclass(frozen=True, slots=True)
class WebConfig:
    """Web server settings; every field can be overridden from the environment."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    debug: bool = False
    watchdog_timeout_ms: int = DEFAULT_WATCHDOG_TIMEOUT_MS
    start_watchdog_monitor: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.port <= 65535:
            raise ValueError("Port must be between 1 and 65535.")
        if self.watchdog_timeout_ms < 1:
            raise ValueError("Watchdog timeout must be at least 1 ms.")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "WebConfig":
        """Build a config from ROVER_WEB_* environment variables."""
        source = os.environ if env is None else env
        return cls(
            host=source.get("ROVER_WEB_HOST", DEFAULT_HOST),
            port=int(source.get("ROVER_WEB_PORT", DEFAULT_PORT)),
            debug=source.get("ROVER_WEB_DEBUG", "").strip().lower() in _TRUE_VALUES,
            watchdog_timeout_ms=int(
                source.get("ROVER_WATCHDOG_TIMEOUT_MS", DEFAULT_WATCHDOG_TIMEOUT_MS)
            ),
        )


@dataclass(slots=True)
class WebServices:
    """Objects shared by the web application, stored in ``app.extensions``."""

    config: WebConfig
    controller: WebRoverController
    socketio: SocketIO
    _stop_event: threading.Event = field(default_factory=threading.Event)

    def start_watchdog_monitor(self) -> None:
        """Poll the command watchdog in a Socket.IO background task."""
        self.socketio.start_background_task(self._watchdog_loop)

    def shutdown(self) -> None:
        """Stop the watchdog monitor and the rover."""
        self._stop_event.set()
        self.controller.safe_stop()

    def _watchdog_loop(self) -> None:
        """Stop the rover and notify clients when drive commands stop arriving."""
        poll_s = min(0.05, self.config.watchdog_timeout_ms / 4000)
        while not self._stop_event.is_set():
            try:
                if self.controller.check_watchdog():
                    broadcast_state(self.socketio, self.controller)
            except Exception:
                logger.exception("Watchdog monitor error; stopping rover.")
                self.controller.safe_stop()
            self.socketio.sleep(poll_s)


def create_app(
    config: WebConfig | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> Flask:
    """Create the Flask app with a simulation-only RoverDrive and Socket.IO.

    ``clock`` drives the command watchdog and can be replaced in tests.
    """
    config = config if config is not None else WebConfig.from_env()
    app = Flask(__name__)
    app.config["DEBUG"] = config.debug

    controller = WebRoverController(
        watchdog_timeout_s=config.watchdog_timeout_ms / 1000,
        clock=clock,
    )
    socketio = SocketIO(app, async_mode="threading")
    register_routes(app, controller)
    register_socketio_events(socketio, controller)

    services = WebServices(config=config, controller=controller, socketio=socketio)
    app.extensions["rover_web"] = services
    if config.start_watchdog_monitor:
        services.start_watchdog_monitor()
    return app

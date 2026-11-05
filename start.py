"""Start the XMW Rover NextGen web interface (simulation only; no hardware access)."""

import argparse
import atexit
import logging
import signal
import sys
from dataclasses import replace
from types import FrameType

from web.app import WebConfig, WebServices, create_app


def parse_args(defaults: WebConfig) -> WebConfig:
    """Apply command-line overrides on top of the environment-based config."""
    parser = argparse.ArgumentParser(description="XMW Rover NextGen web control interface")
    parser.add_argument("--host", default=defaults.host)
    parser.add_argument("--port", type=int, default=defaults.port)
    parser.add_argument("--debug", action="store_true", default=defaults.debug)
    parser.add_argument("--watchdog-timeout-ms", type=int, default=defaults.watchdog_timeout_ms)
    args = parser.parse_args()
    return replace(
        defaults,
        host=args.host,
        port=args.port,
        debug=args.debug,
        watchdog_timeout_ms=args.watchdog_timeout_ms,
    )


def main() -> None:
    """Run the web server until interrupted, always stopping the rover on exit."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = parse_args(WebConfig.from_env())
    app = create_app(config)
    services: WebServices = app.extensions["rover_web"]

    atexit.register(services.shutdown)
    signal.signal(signal.SIGTERM, _exit_on_signal)

    print(f"XMW Rover NextGen web UI: http://localhost:{config.port}")
    print(f"Listening on {config.host}:{config.port} (simulation mode, no hardware access)")
    try:
        services.socketio.run(
            app,
            host=config.host,
            port=config.port,
            debug=config.debug,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )
    finally:
        services.shutdown()


def _exit_on_signal(signum: int, frame: FrameType | None) -> None:
    """Convert SIGTERM into a normal exit so shutdown handlers run."""
    sys.exit(0)


if __name__ == "__main__":
    main()

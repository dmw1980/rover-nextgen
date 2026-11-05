"""Socket.IO event handlers for browser rover control."""

import functools
import logging
from collections.abc import Callable
from typing import Any

from flask_socketio import SocketIO, emit

from web.control import WebRoverController

logger = logging.getLogger(__name__)

STATE_EVENT = "state"


def broadcast_state(socketio: SocketIO, controller: WebRoverController) -> None:
    """Send the current state snapshot to every connected client."""
    socketio.emit(STATE_EVENT, controller.snapshot())


def register_socketio_events(socketio: SocketIO, controller: WebRoverController) -> None:
    """Register all control events; any handler failure stops the rover."""

    def safe_broadcast() -> None:
        try:
            broadcast_state(socketio, controller)
        except Exception:
            logger.exception("Failed to broadcast rover state.")

    def guarded(
        name: str, error_result: dict[str, Any] | None
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Stop the rover and report if a handler raises unexpectedly."""

        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            @functools.wraps(handler)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                try:
                    return handler(*args, **kwargs)
                except Exception:
                    logger.exception("Control event '%s' failed; stopping rover.", name)
                    controller.safe_stop()
                    safe_broadcast()
                    return error_result

            return wrapper

        return decorator

    internal_error = {"ok": False, "error": "Internal control error; rover stopped."}

    @socketio.on("connect")
    @guarded("connect", None)
    def on_connect(auth: Any = None) -> None:
        controller.client_connected()
        broadcast_state(socketio, controller)

    @socketio.on("disconnect")
    @guarded("disconnect", None)
    def on_disconnect(reason: Any = None) -> None:
        controller.client_disconnected()
        broadcast_state(socketio, controller)

    @socketio.on("drive")
    @guarded("drive", internal_error)
    def on_drive(data: Any = None) -> dict[str, Any]:
        result = controller.drive_command(data)
        safe_broadcast()
        return result.to_dict()

    @socketio.on("stop")
    @guarded("stop", internal_error)
    def on_stop(data: Any = None) -> dict[str, Any]:
        result = controller.stop()
        safe_broadcast()
        return result.to_dict()

    @socketio.on("emergency_stop")
    @guarded("emergency_stop", internal_error)
    def on_emergency_stop(data: Any = None) -> dict[str, Any]:
        result = controller.emergency_stop()
        safe_broadcast()
        return result.to_dict()

    @socketio.on("clear_emergency_stop")
    @guarded("clear_emergency_stop", internal_error)
    def on_clear_emergency_stop(data: Any = None) -> dict[str, Any]:
        result = controller.clear_emergency_stop()
        safe_broadcast()
        return result.to_dict()

    @socketio.on("set_speed_mode")
    @guarded("set_speed_mode", internal_error)
    def on_set_speed_mode(data: Any = None) -> dict[str, Any]:
        result = controller.set_speed_mode(data)
        safe_broadcast()
        return result.to_dict()

    @socketio.on("request_state")
    @guarded("request_state", internal_error)
    def on_request_state(data: Any = None) -> dict[str, Any]:
        emit(STATE_EVENT, controller.snapshot())
        return {"ok": True, "error": None}

    @socketio.on_error_default
    def on_unhandled_error(error: Exception) -> None:
        logger.error("Unhandled Socket.IO error; stopping rover.", exc_info=error)
        controller.safe_stop()

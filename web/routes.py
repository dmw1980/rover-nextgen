"""HTTP routes for the rover web interface."""

import time
from typing import Any

from flask import Flask, Response, jsonify, render_template

from web.control import WebRoverController

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; connect-src 'self' ws: wss:; img-src 'self' data:; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)


def register_routes(app: Flask, controller: WebRoverController) -> None:
    """Register the GUI page and read-only JSON endpoints."""

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/api/health")
    def health() -> Response:
        payload: dict[str, Any] = {
            "status": "healthy",
            "service": "rover-nextgen-web",
            "simulation": True,
            "timestamp": time.time(),
        }
        return jsonify(payload)

    @app.get("/api/state")
    def state() -> Response:
        return jsonify(controller.snapshot())

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if response.mimetype == "application/json":
            response.headers["Cache-Control"] = "no-store"
        return response

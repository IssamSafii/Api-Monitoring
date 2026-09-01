from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from routes.compartments import compartments_bp
from routes.instances import instances_bp
from routes.logs import logs_bp
from routes.metrics import metrics_bp
from routes.work_requests import work_requests_bp
from services.oci_client import ApiError


def configure_logging() -> None:
    """Configure application-wide logging."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def create_app() -> Flask:
    """Create and configure the Flask application."""
    configure_logging()
    app = Flask(__name__)
    logger = logging.getLogger(__name__)

    @app.before_request
    def log_request_start() -> None:
        logger.info("Handling %s %s", request.method, request.path)

    @app.after_request
    def log_request_end(response):  # type: ignore[no-untyped-def]
        logger.info(
            "Completed %s %s with status %s",
            request.method,
            request.path,
            response.status_code,
        )
        return response

    @app.get("/health")
    def health() -> tuple[object, int]:
        return (
            jsonify(
                {
                    "status": "healthy",
                    "service": "Safi OCI Monitoring API",
                }
            ),
            200,
        )

    app.register_blueprint(metrics_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(work_requests_bp)
    app.register_blueprint(instances_bp)
    app.register_blueprint(compartments_bp)

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError) -> tuple[object, int]:
        logger.warning("API error: %s", error.message)
        return jsonify({"error": error.message}), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException) -> tuple[object, int]:
        logger.warning("HTTP error: %s", error.description)
        return jsonify({"error": error.description}), error.code or 500

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception) -> tuple[object, int]:
        logger.exception("Unexpected error while handling request", exc_info=error)
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)

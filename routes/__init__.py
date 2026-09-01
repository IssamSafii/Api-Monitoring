"""Route blueprints for the Safi OCI Monitoring API."""

from routes.compartments import compartments_bp
from routes.instances import instances_bp
from routes.logs import logs_bp
from routes.metrics import metrics_bp
from routes.work_requests import work_requests_bp

__all__ = [
    "compartments_bp",
    "instances_bp",
    "logs_bp",
    "metrics_bp",
    "work_requests_bp",
]

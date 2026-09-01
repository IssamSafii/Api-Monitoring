from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.metrics_service import get_metrics

metrics_bp = Blueprint("metrics", __name__)


@metrics_bp.get("/api/metrics")
def metrics() -> tuple[object, int]:
    payload = get_metrics(
        compartment_id=request.args.get("compartment_id"),
        namespace=request.args.get("namespace"),
        query=request.args.get("query"),
        minutes=request.args.get("minutes"),
    )
    return jsonify(payload), 200

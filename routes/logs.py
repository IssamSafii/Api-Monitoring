from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.logs_service import get_logs

logs_bp = Blueprint("logs", __name__)


@logs_bp.get("/api/logs")
def logs() -> tuple[object, int]:
    payload = get_logs(
        compartment_id=request.args.get("compartment_id"),
        query=request.args.get("query"),
        minutes=request.args.get("minutes"),
        limit=request.args.get("limit"),
    )
    return jsonify(payload), 200

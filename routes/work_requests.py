from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.work_requests_service import get_work_requests

work_requests_bp = Blueprint("work_requests", __name__)


@work_requests_bp.get("/api/work-requests")
def work_requests() -> tuple[object, int]:
    payload = get_work_requests(compartment_id=request.args.get("compartment_id"))
    return jsonify(payload), 200

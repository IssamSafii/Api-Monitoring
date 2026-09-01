from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.instances_service import get_instances

instances_bp = Blueprint("instances", __name__)


@instances_bp.get("/api/instances")
def instances() -> tuple[object, int]:
    payload = get_instances(compartment_id=request.args.get("compartment_id"))
    return jsonify(payload), 200

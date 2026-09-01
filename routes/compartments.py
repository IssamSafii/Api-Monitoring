from __future__ import annotations

from flask import Blueprint, jsonify

from services.compartments_service import get_compartments

compartments_bp = Blueprint("compartments", __name__)


@compartments_bp.get("/api/compartments")
def compartments() -> tuple[object, int]:
    payload = get_compartments()
    return jsonify(payload), 200

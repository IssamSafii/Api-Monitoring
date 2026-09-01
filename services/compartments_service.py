from __future__ import annotations

import logging
from typing import Any

from services.oci_client import build_service_error, get_client_manager, list_all_results

logger = logging.getLogger(__name__)


def get_compartments() -> list[dict[str, Any]]:
    """Retrieve accessible compartments recursively from the tenancy root."""
    manager = get_client_manager()

    logger.info(
        "Calling OCI Identity list_compartments recursively from tenancy %s",
        manager.tenancy_id,
    )

    try:
        compartments = list_all_results(
            manager.identity_client.list_compartments,
            compartment_id=manager.tenancy_id,
            compartment_id_in_subtree=True,
            access_level="ANY",
        )
    except Exception as exc:
        raise build_service_error("Unable to retrieve compartments from OCI Identity", exc)

    payload = [_normalize_compartment(item) for item in compartments]
    payload.sort(key=lambda item: ((item.get("name") or "").lower(), item.get("id") or ""))
    logger.info("OCI Identity returned %s compartments", len(payload))
    return payload


def _normalize_compartment(compartment: Any) -> dict[str, Any]:
    """Flatten an OCI compartment summary."""
    return {
        "id": getattr(compartment, "id", None),
        "name": getattr(compartment, "name", None),
        "description": getattr(compartment, "description", None),
        "state": getattr(compartment, "lifecycle_state", None),
        "parentId": getattr(compartment, "compartment_id", None),
    }

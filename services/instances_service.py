from __future__ import annotations

import logging
from typing import Any

from services.oci_client import (
    build_service_error,
    get_client_manager,
    list_all_results,
    normalize_timestamp,
)

logger = logging.getLogger(__name__)


def get_instances(compartment_id: str | None) -> list[dict[str, Any]]:
    """Retrieve and flatten OCI Compute instances."""
    manager = get_client_manager()
    effective_compartment_id = manager.resolve_compartment_id(compartment_id)

    logger.info(
        "Calling OCI Compute list_instances for compartment %s",
        effective_compartment_id,
    )

    try:
        instances = list_all_results(
            manager.compute_client.list_instances,
            compartment_id=effective_compartment_id,
        )
    except Exception as exc:
        raise build_service_error("Unable to retrieve instances from OCI Compute", exc)

    payload = [_normalize_instance(item) for item in instances]
    logger.info("OCI Compute returned %s instances", len(payload))
    return payload


def _normalize_instance(instance: Any) -> dict[str, Any]:
    """Flatten an OCI instance summary."""
    return {
        "id": getattr(instance, "id", None),
        "name": getattr(instance, "display_name", None),
        "state": getattr(instance, "lifecycle_state", None),
        "shape": getattr(instance, "shape", None),
        "availabilityDomain": getattr(instance, "availability_domain", None),
        "compartmentId": getattr(instance, "compartment_id", None),
        "createdAt": normalize_timestamp(getattr(instance, "time_created", None)),
    }

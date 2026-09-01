from __future__ import annotations

import logging
from typing import Any, Callable

import oci

from services.oci_client import (
    ServiceOperationError,
    build_service_error,
    extract_items,
    get_client_manager,
    normalize_timestamp,
    to_plain_dict,
)

logger = logging.getLogger(__name__)

Collector = Callable[[Any, str], list[dict[str, Any]]]


def get_work_requests(compartment_id: str | None) -> list[dict[str, Any]]:
    """Retrieve work requests using supported OCI work request endpoints."""
    manager = get_client_manager()
    effective_compartment_id = manager.resolve_compartment_id(compartment_id)

    logger.info(
        "Retrieving OCI work requests for compartment %s",
        effective_compartment_id,
    )

    collectors: list[Collector] = [
        _collect_generic_work_requests,
        _collect_iam_work_requests,
        # Insert additional service-specific collectors here if you already have
        # working OCI code for services such as DevOps, API Gateway, or Resource Manager.
    ]

    items: dict[str, dict[str, Any]] = {}
    fatal_errors: list[str] = []

    for collector in collectors:
        try:
            for item in collector(manager, effective_compartment_id):
                item_id = item.get("id") or f"{item.get('source')}:{len(items)}"
                items[item_id] = item
        except oci.exceptions.ServiceError as exc:
            if _is_non_fatal_collector_error(exc):
                logger.warning(
                    "Non-fatal work request collector failure from %s: %s",
                    collector.__name__,
                    exc.message,
                )
                continue
            logger.exception(
                "Fatal OCI work request collector failure from %s",
                collector.__name__,
                exc_info=exc,
            )
            fatal_errors.append(build_service_error("Unable to retrieve work requests", exc).message)
        except Exception as exc:
            logger.exception(
                "Unexpected work request collector failure from %s",
                collector.__name__,
                exc_info=exc,
            )
            fatal_errors.append(build_service_error("Unable to retrieve work requests", exc).message)

    payload = list(items.values())
    payload.sort(
        key=lambda item: item.get("timeAccepted") or item.get("timeStarted") or "",
        reverse=True,
    )

    if payload:
        logger.info("Collected %s work requests across supported OCI sources", len(payload))
        return payload

    if fatal_errors:
        raise ServiceOperationError(
            "Work requests are service-specific and the supported OCI collectors failed. "
            + " | ".join(fatal_errors),
            status_code=500,
        )

    logger.info("No work requests returned from supported OCI collectors")
    return []


def _collect_generic_work_requests(manager: Any, compartment_id: str) -> list[dict[str, Any]]:
    """Collect work requests from the generic OCI Work Requests API when available."""
    if manager.work_request_client is None:
        logger.warning("OCI generic WorkRequestClient is not available in this SDK build")
        return []

    response = oci.pagination.list_call_get_all_results(
        manager.work_request_client.list_work_requests,
        compartment_id=compartment_id,
    )
    raw_items = extract_items(response.data)
    return [_normalize_work_request(item, source="generic") for item in raw_items]


def _collect_iam_work_requests(manager: Any, compartment_id: str) -> list[dict[str, Any]]:
    """Collect IAM work requests as a supported service-specific fallback."""
    response = oci.pagination.list_call_get_all_results(
        manager.identity_client.list_iam_work_requests,
        compartment_id=compartment_id,
    )
    raw_items = extract_items(response.data)
    return [_normalize_work_request(item, source="iam") for item in raw_items]


def _normalize_work_request(item: Any, source: str) -> dict[str, Any]:
    """Flatten OCI work request summaries."""
    payload = to_plain_dict(item)

    return {
        "id": _first_value(payload.get("id"), payload.get("work_request_id")),
        "operationType": _first_value(
            payload.get("operation_type"),
            payload.get("operationType"),
            payload.get("action_type"),
        ),
        "status": _first_value(
            payload.get("status"),
            payload.get("lifecycle_state"),
            payload.get("operation_status"),
        ),
        "percentComplete": _first_value(
            payload.get("percent_complete"),
            payload.get("percentComplete"),
        ),
        "timeAccepted": normalize_timestamp(
            _first_value(payload.get("time_accepted"), payload.get("timeAccepted"))
        ),
        "timeStarted": normalize_timestamp(
            _first_value(payload.get("time_started"), payload.get("timeStarted"))
        ),
        "timeFinished": normalize_timestamp(
            _first_value(payload.get("time_finished"), payload.get("timeFinished"))
        ),
        "compartmentId": _first_value(
            payload.get("compartment_id"),
            payload.get("compartmentId"),
        ),
        "source": source,
    }


def _first_value(*values: Any) -> Any:
    """Return the first non-empty value."""
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _is_non_fatal_collector_error(exc: oci.exceptions.ServiceError) -> bool:
    """Treat unsupported or absent work request sources as non-fatal."""
    return exc.status in {404, 409}

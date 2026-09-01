from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import oci

from services.oci_client import (
    build_service_error,
    get_client_manager,
    normalize_timestamp,
    parse_positive_int,
    to_plain_dict,
)

logger = logging.getLogger(__name__)

DEFAULT_MINUTES = 60
DEFAULT_LIMIT = 100


def get_logs(
    compartment_id: str | None,
    query: str | None,
    minutes: str | None,
    limit: str | None,
) -> list[dict[str, Any]]:
    """Retrieve and normalize OCI Logging Search results."""
    manager = get_client_manager()
    effective_compartment_id = manager.resolve_compartment_id(compartment_id)
    effective_minutes = parse_positive_int(minutes, "minutes", DEFAULT_MINUTES)
    effective_limit = parse_positive_int(limit, "limit", DEFAULT_LIMIT)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=effective_minutes)
    search_query = (
        query.strip()
        if query and query.strip()
        else f'search "{effective_compartment_id}" | sort by datetime desc'
    )

    logger.info(
        "Calling OCI Logging Search for compartment %s with limit %s",
        effective_compartment_id,
        effective_limit,
    )

    search_details = oci.loggingsearch.models.SearchLogsDetails(
        time_start=start_time,
        time_end=end_time,
        search_query=search_query,
        is_return_field_info=False,
    )

    raw_results = _search_logs(manager, search_details, effective_limit)
    normalized = [_normalize_log_entry(item) for item in raw_results]
    logger.info("OCI Logging Search returned %s log records", len(normalized))
    return normalized


def _search_logs(
    manager,
    search_details: Any,
    limit: int,
) -> list[Any]:
    """Fetch log search results with pagination up to the requested limit."""
    remaining = limit
    page: str | None = None
    collected: list[Any] = []

    while remaining > 0:
        page_size = min(remaining, 1000)
        try:
            response = manager.logging_client.search_logs(
                search_logs_details=search_details,
                limit=page_size,
                page=page,
            )
        except Exception as exc:
            raise build_service_error("Unable to retrieve logs from OCI Logging Search", exc)

        results = getattr(response.data, "results", []) or []
        collected.extend(results)
        remaining = limit - len(collected)
        page = response.headers.get("opc-next-page")

        if not page or not results:
            break

    return collected[:limit]


def _normalize_log_entry(result: Any) -> dict[str, Any]:
    """Normalize OCI log search results into Grafana-friendly JSON."""
    payload = to_plain_dict(result).get("data")
    if payload is None:
        payload = getattr(result, "data", None)
    if not isinstance(payload, dict):
        payload = {"value": payload} if payload is not None else {}

    nested_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}

    return {
        "timestamp": normalize_timestamp(
            _first_value(
                payload.get("datetime"),
                payload.get("timestamp"),
                nested_data.get("timestamp"),
                nested_data.get("datetime"),
            )
        ),
        "message": _first_value(
            payload.get("message"),
            nested_data.get("message"),
            payload.get("logContent"),
            payload.get("oracle", {}).get("message") if isinstance(payload.get("oracle"), dict) else None,
        ),
        "logId": _first_value(
            payload.get("logId"),
            payload.get("log_id"),
            nested_data.get("logId"),
        ),
        "logGroupId": _first_value(
            payload.get("logGroupId"),
            payload.get("log_group_id"),
            nested_data.get("logGroupId"),
        ),
        "source": _first_value(
            payload.get("source"),
            nested_data.get("source"),
            payload.get("oracle", {}).get("entityName") if isinstance(payload.get("oracle"), dict) else None,
        ),
        "entityId": _first_value(
            payload.get("entityId"),
            nested_data.get("entityId"),
            payload.get("oracle", {}).get("entityId") if isinstance(payload.get("oracle"), dict) else None,
        ),
        "data": payload,
    }


def _first_value(*values: Any) -> Any:
    """Return the first non-empty value."""
    for value in values:
        if value not in (None, ""):
            return value
    return None

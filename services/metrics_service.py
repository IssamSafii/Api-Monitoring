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
)

logger = logging.getLogger(__name__)

DEFAULT_NAMESPACE = "oci_computeagent"
DEFAULT_QUERY = "CpuUtilization[1m].mean()"
DEFAULT_MINUTES = 60


def get_metrics(
    compartment_id: str | None,
    namespace: str | None,
    query: str | None,
    minutes: str | None,
) -> list[dict[str, Any]]:
    """Retrieve and flatten OCI Monitoring metric data."""
    manager = get_client_manager()
    effective_compartment_id = manager.resolve_compartment_id(compartment_id)
    effective_namespace = namespace or DEFAULT_NAMESPACE
    effective_query = query or DEFAULT_QUERY
    effective_minutes = parse_positive_int(minutes, "minutes", DEFAULT_MINUTES)

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=effective_minutes)

    logger.info(
        "Calling OCI Monitoring summarize_metrics_data for compartment %s, namespace %s, query %s",
        effective_compartment_id,
        effective_namespace,
        effective_query,
    )

    details = oci.monitoring.models.SummarizeMetricsDataDetails(
        namespace=effective_namespace,
        query=effective_query,
        start_time=start_time,
        end_time=end_time,
    )

    try:
        response = manager.monitoring_client.summarize_metrics_data(
            compartment_id=effective_compartment_id,
            summarize_metrics_data_details=details,
        )
    except Exception as exc:
        raise build_service_error("Unable to retrieve metrics from OCI Monitoring", exc)

    flattened: list[dict[str, Any]] = []
    for metric in response.data or []:
        dimensions = getattr(metric, "dimensions", {}) or {}
        metadata = getattr(metric, "metadata", {}) or {}

        for datapoint in getattr(metric, "aggregated_datapoints", []) or []:
            flattened.append(
                {
                    "timestamp": normalize_timestamp(getattr(datapoint, "timestamp", None)),
                    "value": getattr(datapoint, "value", None),
                    "metric": getattr(metric, "name", None),
                    "namespace": getattr(metric, "namespace", None),
                    "resourceId": dimensions.get("resourceId"),
                    "resourceName": dimensions.get("resourceDisplayName")
                    or dimensions.get("resourceName"),
                    "compartmentId": getattr(metric, "compartment_id", None),
                    "dimensions": dimensions,
                    "metadata": metadata,
                }
            )

    logger.info("OCI Monitoring returned %s flattened metric datapoints", len(flattened))
    return flattened

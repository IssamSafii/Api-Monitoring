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
DEFAULT_MINUTES = 60

DEFAULT_METRICS = [
    ("CpuUtilization", "mean()"),
    ("MemoryUtilization", "mean()"),
    ("NetworksBytesIn", "sum()"),
    ("NetworksBytesOut", "sum()"),
    ("DiskBytesRead", "sum()"),
    ("DiskBytesWritten", "sum()"),
]


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
    effective_minutes = parse_positive_int(
        minutes,
        "minutes",
        DEFAULT_MINUTES,
    )

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=effective_minutes)

    flattened: list[dict[str, Any]] = []

    #
    # If the caller explicitly provides ?query=...
    # execute only that query.
    #
    if query:
        metric_queries = [query]
    else:
        metric_queries = [
            f"{metric_name}[1m].{statistic}"
            for metric_name, statistic in DEFAULT_METRICS
        ]

    for effective_query in metric_queries:

        logger.info(
            "Calling OCI Monitoring summarize_metrics_data "
            "for compartment %s, namespace %s, query %s",
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
            logger.warning(
                "Unable to retrieve metric query %s: %s",
                effective_query,
                exc,
            )

            # Continue with the other metrics.
            continue

        query_count = 0

        for metric in response.data or []:

            dimensions = getattr(metric, "dimensions", {}) or {}
            metadata = getattr(metric, "metadata", {}) or {}

            metric_name = getattr(metric, "name", None)

            resource_id = (
                dimensions.get("resourceId")
                or dimensions.get("instanceId")
            )

            resource_name = (
                dimensions.get("resourceDisplayName")
                or dimensions.get("resourceName")
                or dimensions.get("displayName")
            )

            for datapoint in (
                getattr(metric, "aggregated_datapoints", []) or []
            ):

                flattened.append(
                    {
                        "timestamp": normalize_timestamp(
                            getattr(datapoint, "timestamp", None)
                        ),
                        "value": getattr(
                            datapoint,
                            "value",
                            None,
                        ),
                        "metric": metric_name,
                        "namespace": getattr(
                            metric,
                            "namespace",
                            None,
                        ),
                        "resourceId": resource_id,
                        "resourceName": resource_name,
                        "compartmentId": getattr(
                            metric,
                            "compartment_id",
                            None,
                        ),
                        "dimensions": dimensions,
                        "metadata": metadata,
                    }
                )

                query_count += 1

        logger.info(
            "Metric query %s returned %s flattened datapoints",
            effective_query,
            query_count,
        )

    logger.info(
        "OCI Monitoring returned %s total flattened metric datapoints",
        len(flattened),
    )

    return flattened
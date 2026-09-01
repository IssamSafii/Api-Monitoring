from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Callable

import oci

try:
    from oci.work_requests import WorkRequestClient
except Exception:  # pragma: no cover - depends on OCI SDK layout at runtime
    WorkRequestClient = None


DEFAULT_OCI_CONFIG_FILE = "~/.oci/config"
DEFAULT_OCI_PROFILE = "DEFAULT"


class ApiError(Exception):
    """Base API error with an HTTP status code."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ConfigurationError(ApiError):
    """Raised when OCI configuration cannot be loaded."""


class RequestValidationError(ApiError):
    """Raised when request parameters are invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class ServiceOperationError(ApiError):
    """Raised when an OCI service call fails."""


class OCIClientManager:
    """Centralized lazy OCI client manager."""

    def __init__(self) -> None:
        self.config_file = os.path.expanduser(
            os.getenv("OCI_CONFIG_FILE", DEFAULT_OCI_CONFIG_FILE)
        )
        self.profile = os.getenv("OCI_PROFILE", DEFAULT_OCI_PROFILE)
        self.default_compartment_id = os.getenv("OCI_COMPARTMENT_ID")

        try:
            self.config = oci.config.from_file(
                file_location=self.config_file,
                profile_name=self.profile,
            )
        except Exception as exc:
            raise ConfigurationError(
                "Unable to load OCI SDK configuration. Check OCI_CONFIG_FILE and OCI_PROFILE."
            ) from exc

        self.tenancy_id = self.config.get("tenancy")
        if not self.tenancy_id:
            raise ConfigurationError(
                "Loaded OCI config does not contain a tenancy OCID."
            )

        self.monitoring_client = oci.monitoring.MonitoringClient(self.config)
        self.logging_client = oci.loggingsearch.LogSearchClient(self.config)
        self.compute_client = oci.core.ComputeClient(self.config)
        self.identity_client = oci.identity.IdentityClient(self.config)
        self.work_request_client = (
            WorkRequestClient(self.config) if WorkRequestClient is not None else None
        )

    def resolve_compartment_id(self, explicit_compartment_id: str | None) -> str:
        """Return the explicit compartment id or the configured default."""
        compartment_id = explicit_compartment_id or self.default_compartment_id
        if not compartment_id:
            raise RequestValidationError(
                "OCI_COMPARTMENT_ID is not configured and no compartment_id query parameter was supplied."
            )
        return compartment_id


@lru_cache(maxsize=1)
def get_client_manager() -> OCIClientManager:
    """Create and cache the OCI client manager."""
    return OCIClientManager()


def parse_positive_int(
    raw_value: str | None,
    field_name: str,
    default: int,
) -> int:
    """Parse a positive integer query parameter."""
    if raw_value is None or raw_value == "":
        return default

    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise RequestValidationError(f"{field_name} must be an integer.") from exc

    if value <= 0:
        raise RequestValidationError(f"{field_name} must be greater than zero.")

    return value


def normalize_timestamp(value: Any) -> str | None:
    """Convert datetimes and epoch values to ISO-8601 strings."""
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )

    if isinstance(value, str):
        return value

    return str(value)


def to_plain_dict(value: Any) -> dict[str, Any]:
    """Convert OCI model objects into plain Python dictionaries."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    try:
        converted = oci.util.to_dict(value)
        if isinstance(converted, dict):
            return converted
    except Exception:
        pass
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def extract_items(payload: Any) -> list[Any]:
    """Extract list items from OCI list-style responses."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    items = getattr(payload, "items", None)
    if isinstance(items, list):
        return items
    return []


def list_all_results(operation: Callable[..., Any], *args: Any, **kwargs: Any) -> list[Any]:
    """Use OCI pagination helpers to fetch all results from list operations."""
    response = oci.pagination.list_call_get_all_results(operation, *args, **kwargs)
    return extract_items(response.data)


def build_service_error(action: str, exc: Exception) -> ServiceOperationError:
    """Convert OCI SDK exceptions into sanitized API errors."""
    if isinstance(exc, oci.exceptions.ServiceError):
        status_code = exc.status if exc.status in {400, 404} else 500
        message = getattr(exc, "message", str(exc))
        error_code = getattr(exc, "code", None)
        request_id = getattr(exc, "opc_request_id", None)

        if error_code == "NotAuthorizedOrNotFound":
            message = (
                f"{message} Likely causes: the compartment OCID is wrong, the compartment "
                "belongs to a different tenancy than the loaded OCI profile, or the OCI user "
                "does not have permission to inspect/list this resource in that compartment."
            )

        if request_id:
            message = f"{message} OCI request id: {request_id}."

        return ServiceOperationError(f"{action}: {message}", status_code=status_code)
    return ServiceOperationError(f"{action}: {str(exc)}", status_code=500)

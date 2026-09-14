# OCI Monitoring API

A lightweight REST API for retrieving monitoring data and resource information from Oracle Cloud Infrastructure (OCI).

Built with Flask and the OCI Python SDK, the service provides normalized JSON responses for metrics, logs, compute instances, compartments, and work requests. It can be used by dashboards, internal tools, automation workflows, or any HTTP client that needs a simple interface to OCI observability data.

## Features

- Retrieve OCI Monitoring metrics over a configurable time range
- Search and normalize OCI log records
- List compute instances and accessible compartments
- Retrieve generic and IAM work requests
- Override the default compartment per request
- Return consistent, integration-friendly JSON
- Run locally, in Docker, or on Kubernetes
- Keep OCI credentials on the backend instead of distributing them to API clients

## Architecture

```text
Dashboard, application, or automation
                 |
                 | HTTP/JSON
                 v
          Flask REST API
                 |
                 | OCI Python SDK
                 v
    Oracle Cloud Infrastructure
```

Only the backend authenticates with OCI. API consumers communicate over HTTP and do not need direct access to the OCI configuration file or private key.

> [!IMPORTANT]
> This service does not currently provide client authentication. Add an API gateway, reverse proxy, network policy, or another suitable access-control layer before exposing it outside a trusted network.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Check whether the service is running |
| `GET` | `/api/metrics` | Retrieve flattened OCI metric data points |
| `GET` | `/api/logs` | Search and normalize OCI logs |
| `GET` | `/api/work-requests` | List supported OCI work requests |
| `GET` | `/api/instances` | List compute instances in a compartment |
| `GET` | `/api/compartments` | List accessible compartments recursively |

Successful data endpoints return JSON arrays. Errors use the following format:

```json
{
  "error": "Error description"
}
```

## Requirements

- Python 3.10 or later
- An OCI account and SDK configuration file
- OCI IAM permissions for each resource type the service will read

## Configuration

The application reads these environment variables:

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `OCI_CONFIG_FILE` | No | `~/.oci/config` | Path to the OCI SDK configuration file |
| `OCI_PROFILE` | No | `DEFAULT` | Profile to load from the configuration file |
| `OCI_COMPARTMENT_ID` | Recommended | None | Default compartment OCID used by data endpoints |
| `LOG_LEVEL` | No | `INFO` | Application logging level |

If `OCI_COMPARTMENT_ID` is not configured, endpoints that operate on a compartment require a `compartment_id` query parameter.

Never commit real OCIDs, OCI configuration files, private keys, or other credentials. Mount credential files at runtime and keep them outside the repository.

## Installation

Clone the repository and enter the project directory:

```bash
git clone <repository-url>
cd oci-monitoring-api
```

Create a virtual environment and install the dependencies:

### Linux and macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set the OCI configuration values before starting the service:

```bash
export OCI_CONFIG_FILE="$HOME/.oci/config"
export OCI_PROFILE="DEFAULT"
export OCI_COMPARTMENT_ID="ocid1.compartment.oc1..example"
```

Run the application:

```bash
python app.py
```

The API is available at `http://localhost:5005`.

## Usage Examples

### Health check

```bash
curl http://localhost:5005/health
```

### Compartments

```bash
curl http://localhost:5005/api/compartments
```

### Compute instances

```bash
curl http://localhost:5005/api/instances
curl "http://localhost:5005/api/instances?compartment_id=ocid1.compartment.oc1..example"
```

### Metrics

Without a `query` parameter, the endpoint requests a default set of compute metrics for the last 60 minutes. The default namespace is `oci_computeagent`.

```bash
curl "http://localhost:5005/api/metrics"
curl "http://localhost:5005/api/metrics?query=CpuUtilization%5B1m%5D.mean%28%29"
curl "http://localhost:5005/api/metrics?query=MemoryUtilization%5B5m%5D.mean%28%29&minutes=180"
curl "http://localhost:5005/api/metrics?namespace=oci_computeagent&compartment_id=ocid1.compartment.oc1..example"
```

Supported query parameters:

| Parameter | Description | Default |
| --- | --- | --- |
| `compartment_id` | Compartment OCID for the request | `OCI_COMPARTMENT_ID` |
| `namespace` | OCI Monitoring namespace | `oci_computeagent` |
| `query` | OCI Monitoring Query Language expression | Built-in compute metric queries |
| `minutes` | Positive integer defining the lookback period | `60` |

### Logs

```bash
curl "http://localhost:5005/api/logs?minutes=60&limit=100"
curl "http://localhost:5005/api/logs?query=search%20%22ocid1.compartment.oc1..example%22%20%7C%20sort%20by%20datetime%20desc"
curl "http://localhost:5005/api/logs?compartment_id=ocid1.compartment.oc1..example&limit=50"
```

Supported query parameters:

| Parameter | Description | Default |
| --- | --- | --- |
| `compartment_id` | Compartment OCID for the request | `OCI_COMPARTMENT_ID` |
| `query` | OCI Logging Search query | Search the selected compartment by newest record |
| `minutes` | Positive integer defining the lookback period | `60` |
| `limit` | Positive integer defining the maximum result count | `100` |

When `query` is omitted, the service uses:

```text
search "<compartment_ocid>" | sort by datetime desc
```

### Work requests

```bash
curl http://localhost:5005/api/work-requests
curl "http://localhost:5005/api/work-requests?compartment_id=ocid1.compartment.oc1..example"
```

OCI work requests are often service-specific. The current implementation checks the generic Work Requests API and then IAM work requests. Additional service-specific collectors can be added in `services/work_requests_service.py`.

## Docker

Build the image:

```bash
docker build -t oci-monitoring-api:latest .
```

Run the container with the local OCI configuration mounted as read-only:

```bash
docker run --rm -p 5005:5005 \
  -e OCI_CONFIG_FILE=/home/app/.oci/config \
  -e OCI_PROFILE=DEFAULT \
  -e OCI_COMPARTMENT_ID=ocid1.compartment.oc1..example \
  -v "$HOME/.oci:/home/app/.oci:ro" \
  oci-monitoring-api:latest
```

Do not copy private keys into the image. Mount the OCI configuration directory and referenced key files when the container starts.

## Kubernetes

Update the image name and credential configuration in `k8s/deployment.yaml`, then apply the manifests:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

The included `ClusterIP` service exposes the API to other workloads in the cluster at:

```text
http://oci-monitoring-api:5005
```

Before deployment, configure:

- A Kubernetes `Secret` containing `OCI_COMPARTMENT_ID`
- A read-only secret or volume containing the OCI configuration file and its referenced private key
- The required network and client access controls for your environment

## Project Structure

```text
oci-monitoring-api/
|-- app.py
|-- requirements.txt
|-- Dockerfile
|-- .dockerignore
|-- .env.example
|-- README.md
|-- routes/
|   |-- compartments.py
|   |-- instances.py
|   |-- logs.py
|   |-- metrics.py
|   `-- work_requests.py
|-- services/
|   |-- compartments_service.py
|   |-- instances_service.py
|   |-- logs_service.py
|   |-- metrics_service.py
|   |-- oci_client.py
|   `-- work_requests_service.py
`-- k8s/
    |-- deployment.yaml
    `-- service.yaml
```

## Supported OCI SDK Operations

- Metrics: `oci.monitoring.MonitoringClient.summarize_metrics_data`
- Logs: `oci.loggingsearch.LogSearchClient.search_logs`
- Compartments: `oci.identity.IdentityClient.list_compartments`
- Instances: `oci.core.ComputeClient.list_instances`
- Work requests: `oci.work_requests.WorkRequestClient.list_work_requests`
- IAM work requests: `oci.identity.IdentityClient.list_iam_work_requests`

## Contributing

Issues and pull requests are welcome. When adding an endpoint, keep responses normalized, avoid exposing sensitive OCI data, and include usage documentation.

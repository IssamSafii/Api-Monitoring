## Architecture

```text
Grafana
   |
   | Infinity datasource
   v
Safi OCI Flask API
   |
   | OCI Python SDK
   v
Oracle Cloud Infrastructure
```

This project is a single Flask application that acts as an API gateway between Grafana Infinity and Oracle Cloud Infrastructure (OCI).

Grafana does not need OCI credentials. Only this backend authenticates to OCI by reading an OCI SDK config file and profile.

## Endpoints

```text
GET /health
GET /api/metrics
GET /api/logs
GET /api/work-requests
GET /api/instances
GET /api/compartments
```

All endpoints return JSON designed to be easy for Grafana Infinity tables, time series panels, and log panels to consume.

## OCI Authentication

The backend reads the following environment variables:

```bash
export OCI_CONFIG_FILE=/home/user/.oci/config
export OCI_PROFILE=DEFAULT
export OCI_COMPARTMENT_ID='ocid1.compartment.oc1..example'
```

Defaults:

```text
OCI_CONFIG_FILE=~/.oci/config
OCI_PROFILE=DEFAULT
```

Do not place real OCI credentials, private keys, or real OCIDs in this repository. Mount the `.oci` directory and key material externally for local Docker or Kubernetes deployments.

## Supported OCI Operations

- Metrics: `oci.monitoring.MonitoringClient.summarize_metrics_data`
- Logs: `oci.loggingsearch.LogSearchClient.search_logs`
- Compartments: `oci.identity.IdentityClient.list_compartments`
- Instances: `oci.core.ComputeClient.list_instances`
- Work requests: `oci.work_requests.WorkRequestClient.list_work_requests` with an IAM fallback through `oci.identity.IdentityClient.list_iam_work_requests`

### Work requests note

OCI work requests are service-specific in many cases. The initial implementation tries the generic Work Requests API first and then falls back to IAM work requests. If your tenancy relies on a service-specific client for work requests, add that collector in [services/work_requests_service.py](/C:/Users/Safi/Desktop/API monitoring/oci-monitoring-api/services/work_requests_service.py).

## Project Structure

```text
oci-monitoring-api/
├── app.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .env.example
├── README.md
├── routes/
│   ├── __init__.py
│   ├── metrics.py
│   ├── logs.py
│   ├── work_requests.py
│   ├── instances.py
│   └── compartments.py
├── services/
│   ├── __init__.py
│   ├── oci_client.py
│   ├── metrics_service.py
│   ├── logs_service.py
│   ├── work_requests_service.py
│   ├── instances_service.py
│   └── compartments_service.py
└── k8s/
    ├── deployment.yaml
    └── service.yaml
```

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Locally

```bash
python app.py
```

The API listens on `0.0.0.0:5005`.

## Endpoint Usage

### Health

```bash
curl http://localhost:5005/health
```

Expected response:

```json
{
  "status": "healthy",
  "service": "Safi OCI Monitoring API"
}
```

### Compartments

```bash
curl http://localhost:5005/api/compartments
```

Example response:

```json
[
  {
    "id": "ocid1.compartment.oc1..example",
    "name": "production",
    "description": "Production compartment",
    "state": "ACTIVE",
    "parentId": "ocid1.tenancy.oc1..example"
  }
]
```

### Instances

```bash
curl http://localhost:5005/api/instances
curl "http://localhost:5005/api/instances?compartment_id=ocid1.compartment.oc1..example"
```

Example response:

```json
[
  {
    "id": "ocid1.instance.oc1..example",
    "name": "vm-01",
    "state": "RUNNING",
    "shape": "VM.Standard.E4.Flex",
    "availabilityDomain": "AD-1",
    "compartmentId": "ocid1.compartment.oc1..example",
    "createdAt": "2026-08-25T10:00:00Z"
  }
]
```

### Metrics

```bash
curl "http://localhost:5005/api/metrics"
curl "http://localhost:5005/api/metrics?query=CpuUtilization%5B1m%5D.mean%28%29"
curl "http://localhost:5005/api/metrics?query=MemoryUtilization%5B5m%5D.mean%28%29&minutes=180"
curl "http://localhost:5005/api/metrics?namespace=oci_computeagent&compartment_id=ocid1.compartment.oc1..example"
```

Example response:

```json
[
  {
    "timestamp": "2026-08-25T10:00:00Z",
    "value": 32.5,
    "metric": "CpuUtilization",
    "namespace": "oci_computeagent",
    "resourceId": "ocid1.instance.oc1..example",
    "resourceName": "vm-01",
    "compartmentId": "ocid1.compartment.oc1..example",
    "dimensions": {
      "resourceId": "ocid1.instance.oc1..example",
      "resourceDisplayName": "vm-01"
    }
  }
]
```

### Logs

```bash
curl "http://localhost:5005/api/logs?minutes=60&limit=100"
curl "http://localhost:5005/api/logs?query=search%20%22ocid1.compartment.oc1..example%22%20%7C%20sort%20by%20datetime%20desc"
curl "http://localhost:5005/api/logs?compartment_id=ocid1.compartment.oc1..example&limit=50"
```

If `query` is omitted, the backend uses a valid OCI Logging Search query in the form:

```text
search "<compartment_ocid>" | sort by datetime desc
```

Example response:

```json
[
  {
    "timestamp": "2026-08-25T10:10:22Z",
    "message": "Example log message",
    "logId": "ocid1.log.oc1..example",
    "logGroupId": "ocid1.loggroup.oc1..example",
    "source": "ocid1.instance.oc1..example",
    "entityId": "ocid1.instance.oc1..example",
    "data": {}
  }
]
```

### Work Requests

```bash
curl http://localhost:5005/api/work-requests
curl "http://localhost:5005/api/work-requests?compartment_id=ocid1.compartment.oc1..example"
```

Example response:

```json
[
  {
    "id": "ocid1.workrequest.oc1..example",
    "operationType": "CREATE_INSTANCE",
    "status": "IN_PROGRESS",
    "percentComplete": 50,
    "timeAccepted": "2026-08-25T10:00:00Z",
    "timeStarted": "2026-08-25T10:01:00Z",
    "timeFinished": null,
    "source": "generic"
  }
]
```

## Docker

Build the image:

```bash
docker build -t oci-monitoring-api:latest .
```

Run the container:

```bash
docker run --rm -p 5005:5005 \
  -e OCI_CONFIG_FILE=/home/app/.oci/config \
  -e OCI_PROFILE=DEFAULT \
  -e OCI_COMPARTMENT_ID=ocid1.compartment.oc1..example \
  -v $HOME/.oci:/home/app/.oci:ro \
  oci-monitoring-api:latest
```

Notes:

- Do not bake OCI private keys into the image.
- Mount the OCI config directory and key files at runtime.

## Kubernetes

Apply the manifests:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

The service is a `ClusterIP` service named `oci-monitoring-api`, which makes the internal Grafana target URL possible:

```text
http://oci-monitoring-api:5005
```

Before deploying, create the image and update the image name in `k8s/deployment.yaml`.

Also wire either:

- a Kubernetes `Secret` for `OCI_COMPARTMENT_ID`, and
- a mounted secret or volume containing `/home/app/.oci/config` and the private key it references

## Grafana Infinity URLs

Use these URLs from Grafana inside the cluster:

```text
http://oci-monitoring-api:5005/api/metrics
http://oci-monitoring-api:5005/api/logs
http://oci-monitoring-api:5005/api/work-requests
http://oci-monitoring-api:5005/api/instances
http://oci-monitoring-api:5005/api/compartments
```

For local development:

```text
http://localhost:5005/api/metrics
http://localhost:5005/api/logs
http://localhost:5005/api/work-requests
http://localhost:5005/api/instances
http://localhost:5005/api/compartments
```

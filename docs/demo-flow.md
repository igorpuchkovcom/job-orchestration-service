# Create/Start/Get Runbook

For the repo-level overview, architecture summary, and setup/testing entrypoints, see [`README.md`](../README.md).

## What This Covers

This runbook walks through one bounded end-to-end flow for the service:

- create a job with a prompt
- start the job
- retrieve the completed job
- confirm the final response contains both a non-null `result_summary` and visible raw `steps`
- demonstrate the versioned API path and demo RBAC headers

The automated path is fake-first and does not require live OpenAI credentials or network access.

## Prerequisites

### Fake-first automated path

- Python 3.13 host environment with dependencies installed
- local PostgreSQL from `docker compose up -d`
- `.env` created from `.env.example`

### Optional live-provider path

- Python 3.13 host environment with dependencies installed
- local PostgreSQL from `docker compose up -d`
- `.env` created from `.env.example`
- `OPENAI_API_KEY`
- optional `OPENAI_MODEL`
- local Redis is recommended and is part of the canonical local environment

The canonical local environment is:

- host Python for the app
- `docker compose` for PostgreSQL and Redis only
- `.env` for local settings

## Fake-First Automated Path

Start the canonical local dependencies:

```powershell
docker compose up -d
```

Copy the env template if you have not already:

```powershell
Copy-Item .env.example .env
```

Run migrations:

```powershell
.\.venv\Scripts\python -m alembic upgrade head
```

Run the end-to-end proof:

```powershell
$env:DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/job_orchestration_service'
.\.venv\Scripts\python -m pytest tests/integration/api/test_demo_flow.py
```

Expected outcome:

- the test passes without `OPENAI_API_KEY`
- the flow proves `POST /api/v1/jobs` -> `POST /api/v1/jobs/{job_id}/start` -> `GET /api/v1/jobs/{job_id}`
- the completed response includes non-null `result_summary`
- raw `steps` remain visible

## Local Run Path

Use the canonical host-Python plus Docker Compose path.

Start the local dependencies:

```powershell
docker compose up -d
```

Create `.env` from the checked-in template if needed:

```powershell
Copy-Item .env.example .env
```

Run migrations:

```powershell
.\.venv\Scripts\python -m alembic upgrade head
```

Start the app:

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Confirm the app is reachable:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health
Invoke-WebRequest http://127.0.0.1:8000/openapi.json
$headers = @{
  "X-Demo-Role" = "operator"
  "X-Demo-Principal" = "local-demo"
}

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/jobs -Headers $headers -ContentType 'application/json' -Body '{"input":{"prompt":"demo"}}'
```

Use a viewer role for read-only fetches if you want to verify RBAC boundaries:

```powershell
$viewerHeaders = @{
  "X-Demo-Role" = "viewer"
  "X-Demo-Principal" = "local-viewer"
}

Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/v1/jobs/<job_id>" -Headers $viewerHeaders
```

Confirm the versioned health endpoint:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health
```

## Docker Run Path

This is a bounded image build/run confirmation using the existing `Dockerfile`.

Create a disposable network and database container:

```powershell
docker network create job-api-runbook-net
docker run --rm -d --network job-api-runbook-net -p 55433:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=job_api_demo --name job-api-demo-db postgres:16
```

Run migrations from the host against the disposable database:

```powershell
$env:DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55433/job_api_demo'
.\.venv\Scripts\python -m alembic upgrade head
```

Build and run the app image:

```powershell
docker build -t job-api-local .
docker run --rm -d --network job-api-runbook-net -p 8005:8000 -e DATABASE_URL='postgresql+psycopg://postgres:postgres@job-api-demo-db:5432/job_api_demo' --name job-api-local-app job-api-local
```

Confirm the containerized app is reachable:

```powershell
Invoke-WebRequest http://127.0.0.1:8005/api/v1/health
```

## Optional Live-Provider Variant

This path is optional and is not part of the automated proof.

Set the provider env vars before starting the local app:

```powershell
$env:OPENAI_API_KEY='your-key'; $env:OPENAI_MODEL='gpt-4o-mini'
```

Create, start, and fetch a job against the running local app:

```powershell
$operatorHeaders = @{
  "X-Demo-Role" = "operator"
  "X-Demo-Principal" = "local-demo"
}

$viewerHeaders = @{
  "X-Demo-Role" = "viewer"
  "X-Demo-Principal" = "local-viewer"
}

$create = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/jobs -Headers $operatorHeaders -ContentType 'application/json' -Body '{"input":{"prompt":"demo"}}'
$started = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/v1/jobs/$($create.id)/start" -Headers $operatorHeaders
$job = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/v1/jobs/$($create.id)" -Headers $viewerHeaders
```

Expected outcome:

- the job transitions from `pending` to `completed`
- the final response contains non-null `result_summary`
- the final response still exposes raw `steps`

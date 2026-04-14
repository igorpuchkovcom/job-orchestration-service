# Create/Start/Get Runbook

For the repo-level overview, architecture summary, and setup/testing entrypoints, see [`README.md`](../README.md).

## What This Covers

This runbook walks through one bounded end-to-end flow for the service:

- create a job with a prompt
- start the job
- retrieve the completed job
- confirm the final response contains both a non-null `result_summary` and visible raw `steps`

The automated path is fake-first and does not require live OpenAI credentials or network access.

## Prerequisites

### Fake-first automated path

- PostgreSQL
- `SHOWCASE_DATABASE_URL`

### Optional live-provider path

- PostgreSQL
- `SHOWCASE_DATABASE_URL`
- `SHOWCASE_OPENAI_API_KEY`
- optional `SHOWCASE_OPENAI_MODEL`
- optional `SHOWCASE_REDIS_URL`

Redis is not required for the fake-first path.

## Fake-First Automated Path

Start a disposable PostgreSQL instance:

```powershell
docker run --rm -d -e POSTGRES_PASSWORD=postgres -e POSTGRES_USER=postgres -e POSTGRES_DB=job_api_test -p 55432:5432 --name job-api-test-db postgres:16
```

Run the end-to-end proof:

```powershell
$env:SHOWCASE_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55432/job_api_test'
.\.venv\Scripts\python -m pytest tests/integration/api/test_demo_flow.py
```

Expected outcome:

- the test passes without `SHOWCASE_OPENAI_API_KEY`
- the flow proves `POST /jobs` -> `POST /jobs/{job_id}/start` -> `GET /jobs/{job_id}`
- the completed response includes non-null `result_summary`
- raw `steps` remain visible

## Local Run Path

Use the existing host Python environment for a practical local boot path.

Set the database URL and run migrations:

```powershell
$env:SHOWCASE_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55432/job_api_test'
.\.venv\Scripts\python -m alembic upgrade head
```

Start the app:

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8004
```

Confirm the app is reachable:

```powershell
Invoke-WebRequest http://127.0.0.1:8004/health
Invoke-WebRequest http://127.0.0.1:8004/openapi.json
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
$env:SHOWCASE_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:55433/job_api_demo'
.\.venv\Scripts\python -m alembic upgrade head
```

Build and run the app image:

```powershell
docker build -t job-api-local .
docker run --rm -d --network job-api-runbook-net -p 8005:8000 -e SHOWCASE_DATABASE_URL='postgresql+psycopg://postgres:postgres@job-api-demo-db:5432/job_api_demo' --name job-api-local-app job-api-local
```

Confirm the containerized app is reachable:

```powershell
Invoke-WebRequest http://127.0.0.1:8005/health
```

## Optional Live-Provider Variant

This path is optional and is not part of the automated proof.

Set the provider env vars before starting the local app:

```powershell
$env:SHOWCASE_OPENAI_API_KEY='your-key'
$env:SHOWCASE_OPENAI_MODEL='gpt-4o-mini'
```

Create, start, and fetch a job against the running local app:

```powershell
$create = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8004/jobs -ContentType 'application/json' -Body '{"input":{"prompt":"demo"}}'
$started = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8004/jobs/$($create.id)/start"
$job = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8004/jobs/$($create.id)"
```

Expected outcome:

- the job transitions from `pending` to `completed`
- the final response contains non-null `result_summary`
- the final response still exposes raw `steps`

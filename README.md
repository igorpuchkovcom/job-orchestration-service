# job-orchestration-service

`job-orchestration-service` is a FastAPI backend for a bounded job-oriented orchestration flow. It exposes a small HTTP API for creating, starting, and querying jobs, persists job and step state in PostgreSQL, executes a provider-backed orchestration step, and returns both raw step data and a small `result_summary` view.

This repository is a deliberately scoped Python reimplementation of the core ideas from a larger orchestration service. It focuses on one coherent service path and a credible operational baseline rather than exact source parity or platform-scale breadth.

## Core Capabilities

- versioned job lifecycle endpoints: `POST /api/v1/jobs`, `POST /api/v1/jobs/{job_id}/start`, `GET /api/v1/jobs/{job_id}`, and `GET /api/v1/health`
- persisted job and step lifecycle state via SQLAlchemy and Alembic
- provider-backed execution through a clear LLM provider boundary
- bounded Redis-backed duplicate-start coordination
- centralized workflow status transitions with explicit validation
- immutable append-only job lifecycle event logging
- standardized API error envelope with global exception normalization
- lightweight demo auth/RBAC boundary suitable for swapping with JWT validation
- read-time `result_summary` alongside raw execution `steps`
- local development, CI, CD, and a small Terraform baseline for one Cloud Run environment

## Architecture Overview

- `app/api/`: HTTP routes and response schemas
- `app/api/auth.py`: demo-only auth and RBAC dependency boundary
- `app/api/errors.py`: API error envelope helpers and exception normalization
- `app/orchestration/`: job lifecycle ownership and execution pipeline
- `app/persistence/`: SQLAlchemy models, session wiring, and repositories
- `app/providers/`: provider contract and implementations
- `app/state/`: Redis-backed coordination helpers
- `app/manifests/`: bounded result shaping
- `app/core/`: settings, lifecycle enums/transitions, and domain event types

API handlers stay thin. Orchestration owns state transitions and execution. Persistence, provider access, and Redis coordination are kept behind explicit boundaries.

## API Versioning And Contracts

- all service routes are mounted under `/api/v1`
- API errors are normalized into one envelope:
  - `code`
  - `message`
  - `details` (optional)
- route handlers still use `HTTPException`, but global exception handlers ensure stable response shape

## Demo Auth And RBAC

This showcase uses a lightweight demo auth boundary that is intentionally simple but explicit:

- `X-Demo-Role` is required
- supported roles: `viewer`, `operator`, `admin`
- `X-Demo-Principal` is optional and defaults to `demo-user`

RBAC policy in the current bounded API:

- `GET /api/v1/jobs/{job_id}`: `viewer`, `operator`, `admin`
- `POST /api/v1/jobs`: `operator`, `admin`
- `POST /api/v1/jobs/{job_id}/start`: `operator`, `admin`

This is not a production identity integration. The dependency boundary is intentionally shaped so it can be replaced by JWT/OIDC/Azure AD token validation later.

## Workflow And Auditability

Workflow status is intentionally bounded and explicit:

- `pending -> running -> completed`
- `pending -> running -> failed`

Invalid transitions are rejected with a conflict response and structured error.

Lifecycle events are append-only in `job_events` and currently include:

- `job_created`
- `job_start_requested`
- `job_started`
- `job_completed`
- `job_failed`
- `job_start_rejected_duplicate`

## Main Flow

1. Create a job with an input payload.
2. Start the job.
3. The orchestration layer executes the provider-backed step and persists the resulting job and step state.
4. Retrieve the completed job and inspect both `result_summary` and raw `steps`.

For a supporting runbook of the create/start/get path, see [`docs/demo-flow.md`](docs/demo-flow.md).

## Tech Stack

- FastAPI
- Pydantic v2 and `pydantic-settings`
- SQLAlchemy 2.x and Alembic
- PostgreSQL
- Redis
- OpenAI Python SDK
- pytest, ruff, and pre-commit
- Docker
- GitHub Actions
- Terraform

## Local Development

The canonical local path uses host Python plus Docker Compose for PostgreSQL and Redis.

### Prerequisites

- Python 3.13
- Docker / Docker Compose

### Setup

```bash
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
docker compose up -d
python -m alembic upgrade head
```

On PowerShell, use `py -3.13 -m venv .venv` and `Copy-Item .env.example .env`.

### Run The Service

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Useful local endpoints:

- `GET /api/v1/health`
- `GET /docs`
- `GET /openapi.json`

Common local configuration lives in `.env`:

- `DATABASE_URL`: required for local runs, migrations, and DB-backed tests
- `REDIS_URL`: recommended for local development and Redis-backed integration coverage
- `REDIS_START_GUARD_TTL_SECONDS`: optional tuning for the duplicate-start guard TTL
- `OPENAI_API_KEY`: only required for the live provider path
- `OPENAI_MODEL`: optional, defaults to `gpt-4o-mini`
- `ENVIRONMENT`: optional, defaults to `development`

The checked-in `.env.example` is wired for the default local Docker Compose services on `127.0.0.1`.

For local job API calls, include demo auth headers, for example:

- `X-Demo-Role: operator`
- `X-Demo-Principal: local-demo`

The repo also includes a small runtime image in `Dockerfile`. For a disposable container runbook, see [`docs/demo-flow.md`](docs/demo-flow.md).

## Testing And Quality Gates

Local test and quality commands:

- lint: `python -m ruff check .`
- unit tests: `python -m pytest tests/unit`
- integration tests: `python -m pytest tests/integration`
- narrow create/start/get proof: `python -m pytest tests/integration/api/test_demo_flow.py`

Local hooks use `pre-commit`:

```bash
python -m pre_commit install
```

Configured local hooks:

- commit-time hook: `python -m ruff check --fix` on Python files
- push-time hook: `python -m pytest tests/unit`

These hooks are intentionally small. They complement CI, but they do not replace it.

The main remote quality gate is `CI / ci`, which runs on pull requests and pushes to `main` and executes:

- `ruff`
- unit tests
- integration tests
- Docker image build

## Deployment Overview

- `main` is the only deploy branch.
- Pull requests are the normal path into `main`.
- Successful `CI` on `main` triggers `CD`.
- `CD` builds and pushes the runtime image, runs `python -m alembic upgrade head`, deploys to Cloud Run, and verifies authenticated `/api/v1/health`.
- `workflow_dispatch` is reserved for manual redeploy or break-glass use from `main`.
- Runtime configuration for the current MVP still comes from GitHub Actions variables and secrets.

The runtime image is intentionally separate from migration execution. Alembic remains a deploy-time responsibility rather than an image-startup responsibility.

## Infrastructure Ownership Model

Terraform under `infra/` owns the long-lived deployment baseline:

- Artifact Registry repository
- Cloud Run service baseline
- runtime service account
- minimum IAM needed for the current deploy path

CD continues to own release-time actions:

- image build and push
- Alembic execution
- `gcloud run deploy`
- post-deploy health verification

The IaC path is intentionally one-environment and import-first. See [`infra/README.md`](infra/README.md) for required variables, import guidance, and the Terraform/CD ownership split.

## Scope And Limitations

- The orchestration flow is intentionally bounded to one fixed provider-backed step instead of the broader planner/executor/evaluator breadth of the original system.
- The repo includes one concrete provider implementation rather than a provider matrix.
- Redis is used only for duplicate-start coordination, not as a generalized workflow state system.
- Auth is intentionally demo-only header-based RBAC, not a full identity provider integration.
- Terraform intentionally excludes database provisioning, Redis provisioning, multi-environment rollout, and broader platform resources.
- This repo is a bounded reimplementation of the service shape and operational model, not a claim of exact production parity.

## Interview Positioning

For backend/systems interviews, this repo is strongest when presented as a focused API service that demonstrates:

- versioned API ownership and predictable error contracts
- explicit state transition control in orchestration flows
- immutable lifecycle audit events
- bounded but realistic Redis coordination for duplicate work prevention
- clean layering with seams for replacing demo auth with real token validation

## Supporting Docs

- [`docs/demo-flow.md`](docs/demo-flow.md): create/start/get runbook and disposable Docker path
- [`infra/README.md`](infra/README.md): Terraform ownership, required variables, and import-first workflow

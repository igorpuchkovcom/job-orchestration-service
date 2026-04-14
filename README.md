# job-orchestration-service

`job-orchestration-service` is a small FastAPI backend inspired by a production orchestration system.

It is a deliberate Python reimplementation optimized for backend architecture, orchestration flow, and interview discussion value rather than exact migration fidelity or production completeness.

## What This Repo Demonstrates

- a bounded job API with `POST /jobs`, `POST /jobs/{job_id}/start`, `GET /jobs/{job_id}`, and `GET /health`
- an orchestration-centric application core with explicit job lifecycle ownership
- persisted job and step state using SQLAlchemy and Alembic
- a real provider boundary with one OpenAI implementation
- a bounded Redis-backed duplicate-start guard
- a small read-time `result_summary` alongside raw execution `steps`
- a fake-first end-to-end demo path that is credible without live API keys

## Architecture At A Glance

- `app/api/`: thin HTTP routes and response schemas
- `app/orchestration/`: job lifecycle, step execution, and composition of providers, persistence, state, and result shaping
- `app/persistence/`: SQLAlchemy models, DB wiring, and repositories
- `app/providers/`: provider contract plus the OpenAI adapter
- `app/state/`: bounded Redis start-guard logic
- `app/manifests/`: demo-friendly result shaping
- `app/core/`: settings and app wiring

This is intentionally small: one main happy path, one real provider, one bounded result view, and no worker platform or deployment framework.

## Main End-To-End Flow

1. Create a job with `POST /jobs`.
2. Start orchestration with `POST /jobs/{job_id}/start`.
3. The orchestration service executes one provider-backed step and persists job and step state.
4. Fetch the completed job with `GET /jobs/{job_id}`.
5. Inspect both the concise `result_summary` and the raw `steps`.

For the detailed walkthrough, see [`docs/demo-flow.md`](docs/demo-flow.md).

## Tech Stack

- FastAPI
- Pydantic v2 and `pydantic-settings`
- SQLAlchemy 2.x and Alembic
- PostgreSQL
- Redis
- OpenAI Python SDK
- pytest and ruff
- Docker

## Quick Setup

The canonical local development path uses host Python plus Docker Compose for PostgreSQL and Redis.
Use Python 3.13 locally to match the existing Docker image.

```bash
python3.13 -m venv .venv
```

PowerShell equivalent:

```powershell
py -3.13 -m venv .venv
```

Activate the environment:

- PowerShell: `.\.venv\Scripts\Activate.ps1`
- bash/zsh: `source .venv/bin/activate`

Install the project and dev tools:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Create a local env file from the template:

```bash
cp .env.example .env
```

PowerShell equivalent:

```powershell
Copy-Item .env.example .env
```

Start local dependencies:

```bash
docker compose up -d
```

## Configuration

The app reads local settings from `.env`. Keep `.env.example` as the source-of-truth template and customize `.env` for your machine.

Common settings for local work:

- `ENVIRONMENT`: optional, defaults to `development`
- `DATABASE_URL`: required for local runs, migrations, and DB-backed tests
- `REDIS_URL`: recommended for local development and required for Redis-backed integration coverage
- `REDIS_START_GUARD_TTL_SECONDS`: optional tuning for the duplicate-start guard TTL
- `OPENAI_API_KEY`: only required for the optional live-provider path
- `OPENAI_MODEL`: optional, defaults to `gpt-4o-mini`

The checked-in `.env.example` is wired for the default local Docker Compose services:

- PostgreSQL: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`

## Database And Migrations

With local dependencies running and `.env` in place, run migrations:

```bash
python -m alembic upgrade head
```

Alembic resolves the database URL from `DATABASE_URL` in `.env`.

## Local Run

With PostgreSQL and Redis running and migrations applied:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Useful endpoints:

- `GET /health`
- `GET /docs`
- `GET /openapi.json`

## Canonical Local Flow

1. Create and activate a Python 3.13 virtual environment.
2. Install dependencies with `python -m pip install -e ".[dev]"`.
3. Copy `.env.example` to `.env`.
4. Start PostgreSQL and Redis with `docker compose up -d`.
5. Run migrations with `python -m alembic upgrade head`.
6. Start the app with `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
7. Verify the environment with `GET /health` or `python -m pytest tests/integration/api/test_demo_flow.py`.

For the integration test path on PowerShell, export `DATABASE_URL` in the current shell before running pytest:

```powershell
$env:DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/job_orchestration_service'
.\.venv\Scripts\python -m pytest tests/integration/api/test_demo_flow.py
```

## Docker Run

Build the image:

```bash
docker build -t job-orchestration-service .
```

The current Docker path is intentionally small:

- start a separate PostgreSQL instance
- run `python -m alembic upgrade head` from the host against that database
- run the app container with `DATABASE_URL` pointing at the database
- use [`docs/demo-flow.md`](docs/demo-flow.md) for the exact disposable Docker walkthrough

Migrations are not baked into the current image.

## Testing

- Lint: `python -m ruff check .`
- Unit tests: `python -m pytest tests/unit`
- Minimal fake-first demo proof: `python -m pytest tests/integration/api/test_demo_flow.py`
  - works with the canonical local Docker Compose PostgreSQL service
  - does not require `OPENAI_API_KEY`
  - does not require Redis
- Broader integration coverage: `python -m pytest tests/integration`
  - requires PostgreSQL
  - Redis-backed tests require `REDIS_URL`, which the canonical `.env` + Docker Compose setup provides

## Deliberate Simplifications And Trade-Offs

- synchronous start execution instead of background workers or queues
- one fixed provider-backed step instead of a broad multi-step pipeline
- one real LLM provider first instead of a provider matrix
- Redis used as a bounded duplicate-start guard, not generalized workflow state
- a small `result_summary` read model instead of a larger artifact or manifest platform
- no exact source parity, infrastructure parity, or production auth/deployment story

## How To Talk About It In An Interview

- Frame it as a deliberate reimplementation inspired by a real orchestration domain, not as a production migration.
- Walk through the main flow: create -> start -> get -> inspect `result_summary` and raw `steps`.
- Highlight the boundaries: thin API layer, orchestration core, provider interface, persistence layer, Redis guard, and read-time result shaping.
- Call out the fake-first testing strategy as an engineering choice: stable automation by default, optional live-provider usage when credentials exist.
- Explain what you would add next for a broader system: background execution, richer pipelines, additional providers, and a stronger runtime/deployment story.

## Further Reading

- detailed demo walkthrough: [`docs/demo-flow.md`](docs/demo-flow.md)

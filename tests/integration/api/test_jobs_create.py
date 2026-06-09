from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence.db import create_session_factory
from app.persistence.repositories.job_repository import JobRepository


def test_create_job_persists_and_returns_bounded_response(
    migrated_engine,
    database_url,
    operator_headers,
) -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/jobs",
        json={"input": {"prompt": "demo"}},
        headers=operator_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["input_payload"] == {"prompt": "demo"}
    assert body["steps"] == []
    assert body["result_summary"] is None
    assert body["job_type"] is None
    assert body["model_id"] is None
    assert body["runtime"] is None
    assert body["resource_profile"] is None


def test_create_job_accepts_optional_inference_metadata(
    migrated_engine,
    database_url,
    operator_headers,
) -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/jobs",
        json={
            "input": {"prompt": "demo"},
            "job_type": "inference",
            "model_id": "openai:gpt-4o-mini",
            "runtime": "openai_api",
            "resource_profile": "cpu-small",
        },
        headers=operator_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["input_payload"] == {
        "prompt": "demo",
        "_inference": {
            "job_type": "inference",
            "model_id": "openai:gpt-4o-mini",
            "runtime": "openai_api",
            "resource_profile": "cpu-small",
        },
    }
    assert body["job_type"] == "inference"
    assert body["model_id"] == "openai:gpt-4o-mini"
    assert body["runtime"] == "openai_api"
    assert body["resource_profile"] == "cpu-small"


def test_jobs_routes_are_visible_in_openapi() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/jobs" in paths
    assert "/api/v1/jobs/{job_id}" in paths
    assert "/api/v1/jobs/{job_id}/start" in paths


def test_create_job_records_created_event(
    migrated_engine,
    database_url,
    operator_headers,
) -> None:
    session_factory = create_session_factory(migrated_engine)
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/jobs",
        json={"input": {"prompt": "demo"}},
        headers=operator_headers,
    )

    assert response.status_code == 201
    job_id = UUID(response.json()["id"])

    with session_factory() as session:
        job = JobRepository(session).get_job(job_id)
        assert job is not None
        assert [event.event_type for event in job.events] == ["job_created"]

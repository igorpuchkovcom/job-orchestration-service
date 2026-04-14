from fastapi.testclient import TestClient

from app.main import create_app
from app.persistence.db import create_session_factory
from app.persistence.repositories.job_repository import JobRepository, JobStepCreate


def test_get_job_returns_bounded_schema_shaped_response(migrated_engine, database_url) -> None:
    session_factory = create_session_factory(migrated_engine)

    with session_factory() as session:
        job = JobRepository(session).create_job(
            status="pending",
            input_payload={"prompt": "demo"},
            steps=[JobStepCreate(step_key="prepare", step_index=1, status="pending")],
        )
        job_id = job.id
        session.commit()

    client = TestClient(create_app())
    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(job_id)
    assert body["status"] == "pending"
    assert body["input_payload"] == {"prompt": "demo"}
    assert body["steps"][0]["step_key"] == "prepare"
    assert body["result_summary"] is None


def test_get_job_returns_result_summary_for_completed_job(migrated_engine, database_url) -> None:
    session_factory = create_session_factory(migrated_engine)

    with session_factory() as session:
        job = JobRepository(session).create_job(
            status="completed",
            input_payload={"prompt": "demo"},
            steps=[
                JobStepCreate(
                    step_key="llm_generate_text",
                    step_index=1,
                    status="completed",
                    output_payload={
                        "provider": "openai",
                        "model": "test-model",
                        "content": "provider-backed content",
                    },
                )
            ],
        )
        job_id = job.id
        session.commit()

    client = TestClient(create_app())
    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["result_summary"] == {
        "provider": "openai",
        "model": "test-model",
        "content": "provider-backed content",
    }
    assert body["steps"][0]["output_payload"] == {
        "provider": "openai",
        "model": "test-model",
        "content": "provider-backed content",
    }


def test_get_job_returns_null_result_summary_for_completed_job_with_missing_fields(
    migrated_engine,
    database_url,
) -> None:
    session_factory = create_session_factory(migrated_engine)

    with session_factory() as session:
        job = JobRepository(session).create_job(
            status="completed",
            input_payload={"prompt": "demo"},
            steps=[
                JobStepCreate(
                    step_key="llm_generate_text",
                    step_index=1,
                    status="completed",
                    output_payload={
                        "provider": "openai",
                        "content": "provider-backed content",
                    },
                )
            ],
        )
        job_id = job.id
        session.commit()

    client = TestClient(create_app())
    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["result_summary"] is None


def test_get_job_returns_404_for_unknown_id(migrated_engine, database_url) -> None:
    client = TestClient(create_app())
    response = client.get("/jobs/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found."}

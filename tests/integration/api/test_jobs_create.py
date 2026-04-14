from fastapi.testclient import TestClient

from app.main import create_app


def test_create_job_persists_and_returns_bounded_response(migrated_engine, database_url) -> None:
    client = TestClient(create_app())

    response = client.post("/jobs", json={"input": {"prompt": "demo"}})

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "pending"
    assert body["input_payload"] == {"prompt": "demo"}
    assert body["steps"] == []
    assert body["result_summary"] is None


def test_jobs_routes_are_visible_in_openapi() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/jobs" in paths
    assert "/jobs/{job_id}" in paths
    assert "/jobs/{job_id}/start" in paths

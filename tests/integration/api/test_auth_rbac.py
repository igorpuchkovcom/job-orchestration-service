from fastapi.testclient import TestClient

from app.main import create_app


def test_create_job_requires_demo_role_header() -> None:
    client = TestClient(create_app())

    response = client.post("/api/v1/jobs", json={"input": {"prompt": "demo"}})

    assert response.status_code == 401
    assert response.json() == {
        "code": "missing_role",
        "message": "Missing X-Demo-Role header.",
        "details": None,
    }


def test_create_job_rejects_invalid_demo_role() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/jobs",
        json={"input": {"prompt": "demo"}},
        headers={"X-Demo-Role": "guest"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "code": "invalid_role",
        "message": "Invalid demo role.",
        "details": {"allowed_roles": ["viewer", "operator", "admin"]},
    }


def test_create_job_denies_viewer_role(viewer_headers) -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/jobs",
        json={"input": {"prompt": "demo"}},
        headers=viewer_headers,
    )

    assert response.status_code == 403
    assert response.json() == {
        "code": "forbidden",
        "message": "Role is not allowed for this operation.",
        "details": {"role": "viewer", "required_roles": ["admin", "operator"]},
    }


def test_create_job_allows_operator_role(migrated_engine, database_url, operator_headers) -> None:
    assert migrated_engine is not None
    assert database_url
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/jobs",
        json={"input": {"prompt": "demo"}},
        headers=operator_headers,
    )

    assert response.status_code == 201


def test_viewer_can_read_jobs_but_cannot_start_them(
    migrated_engine,
    database_url,
    operator_headers,
    viewer_headers,
) -> None:
    assert migrated_engine is not None
    assert database_url
    client = TestClient(create_app())

    create_response = client.post(
        "/api/v1/jobs",
        json={"input": {"prompt": "demo"}},
        headers=operator_headers,
    )
    assert create_response.status_code == 201
    job_id = create_response.json()["id"]

    read_response = client.get(f"/api/v1/jobs/{job_id}", headers=viewer_headers)
    assert read_response.status_code == 200

    start_response = client.post(f"/api/v1/jobs/{job_id}/start", headers=viewer_headers)
    assert start_response.status_code == 403
    assert start_response.json() == {
        "code": "forbidden",
        "message": "Role is not allowed for this operation.",
        "details": {"role": "viewer", "required_roles": ["admin", "operator"]},
    }


def test_validation_errors_use_standard_error_envelope(viewer_headers) -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/jobs/not-a-uuid", headers=viewer_headers)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "Request validation failed."
    assert isinstance(body["details"], list)

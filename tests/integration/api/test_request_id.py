from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app


def _client_with_error_route() -> TestClient:
    app: FastAPI = create_app()

    @app.get("/_test/unhandled", include_in_schema=False)
    def _raise_unhandled_error() -> None:
        raise RuntimeError("forced test error")

    return TestClient(app, raise_server_exceptions=False)


def test_missing_request_id_header_is_generated() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    response_request_id = response.headers.get("X-Request-ID")
    assert response_request_id is not None
    assert UUID(response_request_id)


def test_request_id_header_is_propagated() -> None:
    client = TestClient(create_app())
    request_id = "interview-request-id-123"

    response = client.get("/api/v1/health", headers={"X-Request-ID": request_id})

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == request_id


def test_unhandled_500_error_includes_request_id_in_details() -> None:
    client = _client_with_error_route()
    request_id = "request-500-test"

    response = client.get("/_test/unhandled", headers={"X-Request-ID": request_id})

    assert response.status_code == 500
    assert response.headers.get("X-Request-ID") == request_id
    assert response.json() == {
        "code": "internal_error",
        "message": "Internal server error.",
        "details": {"request_id": request_id},
    }


def test_unhandled_exception_is_logged_with_request_context(caplog) -> None:
    client = _client_with_error_route()
    request_id = "request-log-test"
    caplog.set_level("ERROR", logger="app.api.errors")

    response = client.get("/_test/unhandled", headers={"X-Request-ID": request_id})

    assert response.status_code == 500
    record = next(record for record in caplog.records if record.message == "unhandled_exception")
    assert getattr(record, "request_id", None) == request_id
    assert getattr(record, "method", None) == "GET"
    assert getattr(record, "path", None) == "/_test/unhandled"
    assert getattr(record, "exception_type", None) == "RuntimeError"


def test_error_envelope_shape_for_http_exceptions_is_unchanged() -> None:
    client = TestClient(create_app())

    response = client.post("/api/v1/jobs", json={"input": {"prompt": "demo"}})

    assert response.status_code == 401
    assert response.json() == {
        "code": "missing_role",
        "message": "Missing X-Demo-Role header.",
        "details": None,
    }

from fastapi.testclient import TestClient

from app.main import create_app
from app.orchestration.services.orchestration_service import OrchestrationService
from app.persistence.repositories.job_repository import JobRepository
from app.providers.llm.openai_provider import LLMGenerationResult
from app.state.redis_state import RedisStartGuard


def test_demo_flow_proves_create_start_get_happy_path(
    migrated_engine,
    database_url,
    monkeypatch,
) -> None:
    assert migrated_engine is not None
    assert database_url

    monkeypatch.setattr(
        OrchestrationService,
        "__init__",
        _fake_service_init_success,
    )

    client = TestClient(create_app())

    create_response = client.post("/jobs", json={"input": {"prompt": "demo"}})
    assert create_response.status_code == 201
    created = create_response.json()
    job_id = created["id"]

    assert created["status"] == "pending"
    assert created["input_payload"] == {"prompt": "demo"}
    assert created["steps"] == []
    assert created["result_summary"] is None
    assert created["started_at"] is None
    assert created["completed_at"] is None

    expected_result = {
        "provider": "openai",
        "model": "test-model",
        "content": "provider-backed content",
    }

    start_response = client.post(f"/jobs/{job_id}/start")
    assert start_response.status_code == 200
    started = start_response.json()

    assert started["id"] == job_id
    assert started["status"] == "completed"
    assert started["input_payload"] == {"prompt": "demo"}
    assert started["started_at"] is not None
    assert started["completed_at"] is not None
    assert started["result_summary"] == expected_result
    assert len(started["steps"]) == 1
    assert started["steps"][0]["step_key"] == "llm_generate_text"
    assert started["steps"][0]["status"] == "completed"
    assert started["steps"][0]["output_payload"] == expected_result

    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    retrieved = get_response.json()

    assert retrieved["id"] == job_id
    assert retrieved["status"] == "completed"
    assert retrieved["input_payload"] == {"prompt": "demo"}
    assert retrieved["started_at"] == started["started_at"]
    assert retrieved["completed_at"] == started["completed_at"]
    assert retrieved["result_summary"] == started["result_summary"]
    assert retrieved["steps"] == started["steps"]


def _fake_service_init_success(self, session) -> None:
    self.repository = JobRepository(session)
    self.settings = None
    self.provider_factory = lambda: _FakeProvider(
        result=LLMGenerationResult(
            provider="openai",
            model="test-model",
            content="provider-backed content",
        )
    )
    self.start_guard = RedisStartGuard(redis_url=None, ttl_seconds=30)

    from app.orchestration.pipeline.executor import OrchestrationExecutor

    self.executor = OrchestrationExecutor(self.repository, self.provider_factory)


class _FakeProvider:
    def __init__(self, *, result: LLMGenerationResult) -> None:
        self.result = result

    def generate_text(self, prompt: str) -> LLMGenerationResult:
        assert prompt == "demo"
        return self.result

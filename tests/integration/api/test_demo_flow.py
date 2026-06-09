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
    operator_headers,
    viewer_headers,
) -> None:
    assert migrated_engine is not None
    assert database_url

    monkeypatch.setattr(
        OrchestrationService,
        "__init__",
        _fake_service_init_success,
    )

    client = TestClient(create_app())

    create_response = client.post(
        "/api/v1/jobs",
        json={"input": {"prompt": "demo"}},
        headers=operator_headers,
    )
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
        "tokens_in": 11,
        "tokens_out": 7,
        "total_tokens": 18,
    }

    start_response = client.post(
        f"/api/v1/jobs/{job_id}/start",
        headers=operator_headers,
    )
    assert start_response.status_code == 200
    started = start_response.json()

    assert started["id"] == job_id
    assert started["status"] == "completed"
    assert started["input_payload"] == {"prompt": "demo"}
    assert started["started_at"] is not None
    assert started["completed_at"] is not None
    assert started["result_summary"]["provider"] == expected_result["provider"]
    assert started["result_summary"]["model"] == expected_result["model"]
    assert started["result_summary"]["content"] == expected_result["content"]
    assert started["result_summary"]["tokens_in"] == expected_result["tokens_in"]
    assert started["result_summary"]["tokens_out"] == expected_result["tokens_out"]
    assert started["result_summary"]["total_tokens"] == expected_result["total_tokens"]
    assert isinstance(started["result_summary"]["latency_ms"], int)
    assert started["result_summary"]["latency_ms"] >= 0
    assert len(started["steps"]) == 1
    assert started["steps"][0]["step_key"] == "llm_generate_text"
    assert started["steps"][0]["status"] == "completed"
    output_payload = started["steps"][0]["output_payload"]
    assert output_payload["provider"] == expected_result["provider"]
    assert output_payload["model"] == expected_result["model"]
    assert output_payload["content"] == expected_result["content"]
    assert output_payload["tokens_in"] == expected_result["tokens_in"]
    assert output_payload["tokens_out"] == expected_result["tokens_out"]
    assert output_payload["total_tokens"] == expected_result["total_tokens"]
    assert isinstance(output_payload["latency_ms"], int)
    assert output_payload["latency_ms"] >= 0

    get_response = client.get(f"/api/v1/jobs/{job_id}", headers=viewer_headers)
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
            usage={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
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

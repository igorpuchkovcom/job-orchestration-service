from fastapi.testclient import TestClient

from app.main import create_app
from app.orchestration.services.orchestration_service import OrchestrationService
from app.persistence.db import create_session_factory
from app.persistence.repositories.job_repository import JobRepository
from app.providers.llm.openai_provider import LLMGenerationResult
from app.state.redis_state import RedisStartGuard


def test_start_route_delegates_to_orchestration_and_completes_flow(
    migrated_engine,
    database_url,
    monkeypatch,
    operator_headers,
) -> None:
    session_factory = create_session_factory(migrated_engine)

    monkeypatch.setattr(
        OrchestrationService,
        "__init__",
        _fake_service_init_success,
    )

    with session_factory() as session:
        job = JobRepository(session).create_job(status="pending", input_payload={"prompt": "demo"})
        job_id = job.id
        session.commit()

    client = TestClient(create_app())
    response = client.post(f"/api/v1/jobs/{job_id}/start", headers=operator_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(job_id)
    assert body["status"] == "completed"
    assert len(body["steps"]) == 1
    assert body["steps"][0]["step_key"] == "llm_generate_text"
    assert body["steps"][0]["status"] == "completed"
    assert body["steps"][0]["output_payload"] == {
        "provider": "openai",
        "model": "test-model",
        "content": "provider-backed content",
    }


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
    def __init__(
        self,
        *,
        result: LLMGenerationResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error

    def generate_text(self, prompt: str) -> LLMGenerationResult:
        assert prompt == "demo"
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("Expected fake provider result.")
        return self.result

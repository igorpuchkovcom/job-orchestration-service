from app.orchestration.services.orchestration_service import OrchestrationService
from app.persistence.db import create_session_factory
from app.persistence.repositories.job_repository import JobRepository
from app.providers.llm.openai_provider import LLMGenerationResult


def test_orchestration_service_persists_completed_flow_for_pending_job(migrated_engine) -> None:
    session_factory = create_session_factory(migrated_engine)

    with session_factory() as session:
        repository = JobRepository(session)
        job = repository.create_job(status="pending", input_payload={"prompt": "demo"})
        job_id = job.id

        OrchestrationService(
            session,
            provider_factory=lambda: _FakeProvider(
                result=LLMGenerationResult(
                    provider="openai",
                    model="test-model",
                    content="provider-backed content",
                )
            ),
        ).start_job(job_id)
        session.commit()

    with session_factory() as session:
        reloaded_job = JobRepository(session).get_job(job_id)

        assert reloaded_job is not None
        assert reloaded_job.status == "completed"
        assert len(reloaded_job.steps) == 1
        assert reloaded_job.steps[0].step_index == 1
        assert reloaded_job.steps[0].status == "completed"
        assert reloaded_job.steps[0].error_payload is None
        assert reloaded_job.steps[0].step_key == "llm_generate_text"
        assert reloaded_job.steps[0].output_payload == {
            "provider": "openai",
            "model": "test-model",
            "content": "provider-backed content",
        }
        assert [event.event_type for event in reloaded_job.events] == [
            "job_start_requested",
            "job_started",
            "job_completed",
        ]


def test_orchestration_service_persists_failed_flow_for_provider_error(migrated_engine) -> None:
    session_factory = create_session_factory(migrated_engine)

    with session_factory() as session:
        repository = JobRepository(session)
        job = repository.create_job(status="pending", input_payload={"prompt": "demo"})
        job_id = job.id

        OrchestrationService(
            session,
            provider_factory=lambda: _FakeProvider(error=RuntimeError("provider unavailable")),
        ).start_job(job_id)
        session.commit()

    with session_factory() as session:
        reloaded_job = JobRepository(session).get_job(job_id)

        assert reloaded_job is not None
        assert reloaded_job.status == "failed"
        assert len(reloaded_job.steps) == 1
        assert reloaded_job.steps[0].step_key == "llm_generate_text"
        assert reloaded_job.steps[0].status == "failed"
        assert reloaded_job.steps[0].output_payload is None
        assert reloaded_job.steps[0].error_payload == {
            "type": "RuntimeError",
            "message": "provider unavailable",
        }
        assert [event.event_type for event in reloaded_job.events] == [
            "job_start_requested",
            "job_started",
            "job_failed",
        ]


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

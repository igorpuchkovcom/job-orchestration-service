from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from app.orchestration.pipeline.executor import OrchestrationExecutor
from app.providers.llm.openai_provider import LLMGenerationResult


@dataclass
class FakeJob:
    id: UUID
    status: str
    input_payload: dict[str, object]
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class FakeJobStep:
    id: UUID
    job_id: UUID
    step_key: str
    step_index: int
    status: str
    output_payload: dict | None = None
    error_payload: dict | None = None


class FakeJobRepository:
    def __init__(self, job: FakeJob | None) -> None:
        self.job = job
        self.steps: list[FakeJobStep] = []
        self.events: list[tuple[str, dict | None]] = []

    def get_job(self, job_id: UUID) -> FakeJob | None:
        if self.job is None or self.job.id != job_id:
            return None
        return self.job

    def update_job_status(
        self,
        job_id: UUID,
        *,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> FakeJob:
        if self.job is None or self.job.id != job_id:
            raise LookupError(f"Job not found: {job_id}")

        self.job.status = status
        if started_at is not None:
            self.job.started_at = started_at
        if completed_at is not None:
            self.job.completed_at = completed_at
        return self.job

    def create_job_step(
        self,
        job_id: UUID,
        *,
        step_key: str,
        step_index: int,
        status: str,
        output_payload: dict | None = None,
        error_payload: dict | None = None,
    ) -> FakeJobStep:
        if self.job is None or self.job.id != job_id:
            raise LookupError(f"Job not found: {job_id}")

        step = FakeJobStep(
            id=uuid4(),
            job_id=job_id,
            step_key=step_key,
            step_index=step_index,
            status=status,
            output_payload=output_payload,
            error_payload=error_payload,
        )
        self.steps.append(step)
        return step

    def update_job_step(
        self,
        step_id: UUID,
        *,
        status: str,
        output_payload: dict | None = None,
        error_payload: dict | None = None,
    ) -> FakeJobStep:
        for step in self.steps:
            if step.id == step_id:
                step.status = status
                step.output_payload = output_payload
                step.error_payload = error_payload
                return step
        raise LookupError(f"JobStep not found: {step_id}")

    def create_job_event(
        self,
        job_id: UUID,
        *,
        event_type: str,
        event_payload: dict | None = None,
    ) -> None:
        if self.job is None or self.job.id != job_id:
            raise LookupError(f"Job not found: {job_id}")
        self.events.append((event_type, event_payload))


class FakeProvider:
    def __init__(
        self,
        *,
        result: LLMGenerationResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.prompts: list[str] = []

    def generate_text(self, prompt: str) -> LLMGenerationResult:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise AssertionError("FakeProvider needs a result or an error.")
        return self.result


def test_executor_runs_provider_backed_flow_and_updates_in_memory_state() -> None:
    job = FakeJob(id=uuid4(), status="pending", input_payload={"prompt": "demo prompt"})
    repository = FakeJobRepository(job)
    provider = FakeProvider(
        result=LLMGenerationResult(
            provider="openai",
            model="test-model",
            content="provider-backed content",
        )
    )

    OrchestrationExecutor(repository, lambda: provider).start_job(job.id)

    assert provider.prompts == ["demo prompt"]
    assert job.status == "completed"
    assert job.started_at is not None
    assert job.completed_at is not None
    assert len(repository.steps) == 1
    assert repository.steps[0].step_key == "llm_generate_text"
    assert repository.steps[0].status == "completed"
    assert repository.steps[0].output_payload == {
        "provider": "openai",
        "model": "test-model",
        "content": "provider-backed content",
    }
    assert repository.steps[0].error_payload is None
    assert repository.events == [("job_started", None), ("job_completed", None)]


def test_executor_marks_job_and_step_failed_for_provider_error() -> None:
    job = FakeJob(id=uuid4(), status="pending", input_payload={"prompt": "demo prompt"})
    repository = FakeJobRepository(job)
    provider = FakeProvider(error=RuntimeError("provider unavailable"))

    OrchestrationExecutor(repository, lambda: provider).start_job(job.id)

    assert job.status == "failed"
    assert job.started_at is not None
    assert job.completed_at is not None
    assert len(repository.steps) == 1
    assert repository.steps[0].step_key == "llm_generate_text"
    assert repository.steps[0].status == "failed"
    assert repository.steps[0].output_payload is None
    assert repository.steps[0].error_payload == {
        "type": "RuntimeError",
        "message": "provider unavailable",
    }
    assert repository.events == [
        ("job_started", None),
        ("job_failed", {"type": "RuntimeError", "message": "provider unavailable"}),
    ]


def test_executor_rejects_non_pending_jobs() -> None:
    job = FakeJob(id=uuid4(), status="running", input_payload={"prompt": "demo"})
    repository = FakeJobRepository(job)
    provider = FakeProvider(
        result=LLMGenerationResult(
            provider="openai",
            model="test-model",
            content="provider-backed content",
        )
    )

    try:
        OrchestrationExecutor(repository, lambda: provider).start_job(job.id)
    except ValueError as error:
        assert str(error) == f"Invalid job status transition: {job.status} -> running"
    else:
        raise AssertionError("Expected ValueError for non-pending job")


def test_executor_raises_lookup_for_unknown_job() -> None:
    repository = FakeJobRepository(job=None)
    provider = FakeProvider(
        result=LLMGenerationResult(
            provider="openai",
            model="test-model",
            content="provider-backed content",
        )
    )

    try:
        OrchestrationExecutor(repository, lambda: provider).start_job(uuid4())
    except LookupError as error:
        assert "Job not found" in str(error)
    else:
        raise AssertionError("Expected LookupError for unknown job")

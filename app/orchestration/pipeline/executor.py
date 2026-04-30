import json
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from app.core.job_events import JobEventType
from app.core.job_lifecycle import JobStatus, JobStepStatus, ensure_job_transition
from app.orchestration.pipeline.steps import FIXED_FLOW
from app.persistence.repositories.job_repository import JobRepository
from app.providers.llm.openai_provider import LLMGenerationResult, LLMProvider

ProviderFactory = Callable[[], LLMProvider]


class OrchestrationExecutor:
    def __init__(self, repository: JobRepository, provider_factory: ProviderFactory) -> None:
        self.repository = repository
        self.provider_factory = provider_factory

    def start_job(self, job_id: UUID) -> None:
        job = self.repository.get_job(job_id)
        if job is None:
            raise LookupError(f"Job not found: {job_id}")

        ensure_job_transition(job.status, JobStatus.RUNNING)

        self.repository.update_job_status(
            job_id,
            status=JobStatus.RUNNING,
            started_at=datetime.now(UTC),
        )
        self.repository.create_job_event(
            job_id,
            event_type=JobEventType.JOB_STARTED.value,
        )

        for index, step_definition in enumerate(FIXED_FLOW, start=1):
            job_step = self.repository.create_job_step(
                job_id,
                step_key=step_definition.step_key,
                step_index=index,
                status=JobStepStatus.RUNNING,
            )

            try:
                generation = self.provider_factory().generate_text(
                    self._build_prompt(job.input_payload)
                )
            except Exception as error:
                self.repository.update_job_step(
                    job_step.id,
                    status=JobStepStatus.FAILED,
                    output_payload=None,
                    error_payload=self._build_error_payload(error),
                )
                self.repository.update_job_status(
                    job_id,
                    status=JobStatus.FAILED,
                    completed_at=datetime.now(UTC),
                )
                self.repository.create_job_event(
                    job_id,
                    event_type=JobEventType.JOB_FAILED.value,
                    event_payload=self._build_error_payload(error),
                )
                return

            self.repository.update_job_step(
                job_step.id,
                status=JobStepStatus.COMPLETED,
                output_payload=self._build_output_payload(generation),
                error_payload=None,
            )

        self.repository.update_job_status(
            job_id,
            status=JobStatus.COMPLETED,
            completed_at=datetime.now(UTC),
        )
        self.repository.create_job_event(
            job_id,
            event_type=JobEventType.JOB_COMPLETED.value,
        )

    @staticmethod
    def _build_prompt(input_payload: dict[str, object]) -> str:
        prompt = input_payload.get("prompt")
        if isinstance(prompt, str) and prompt.strip():
            return prompt.strip()
        return json.dumps(input_payload, sort_keys=True)

    @staticmethod
    def _build_output_payload(generation: LLMGenerationResult) -> dict[str, object]:
        payload: dict[str, object] = {
            "provider": generation.provider,
            "model": generation.model,
            "content": generation.content,
        }
        if generation.usage is not None:
            payload["usage"] = generation.usage
        return payload

    @staticmethod
    def _build_error_payload(error: Exception) -> dict[str, str]:
        return {
            "type": error.__class__.__name__,
            "message": str(error) or "Provider-backed execution failed.",
        }

from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.job_events import JobEventType
from app.core.job_lifecycle import JobStatus, ensure_job_transition
from app.orchestration.pipeline.executor import OrchestrationExecutor
from app.persistence.repositories.job_repository import JobRepository
from app.providers.llm.openai_provider import LLMProvider, OpenAIProvider
from app.state.redis_state import RedisStartGuard

ProviderFactory = Callable[[], LLMProvider]


def create_default_provider(settings: Settings) -> LLMProvider:
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
    )


def create_default_start_guard(settings: Settings) -> RedisStartGuard:
    return RedisStartGuard(
        redis_url=settings.redis_url,
        ttl_seconds=settings.redis_start_guard_ttl_seconds,
    )


class DuplicateJobStartError(ValueError):
    pass


class OrchestrationService:
    def __init__(
        self,
        session: Session,
        *,
        settings: Settings | None = None,
        provider_factory: ProviderFactory | None = None,
        start_guard: RedisStartGuard | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repository = JobRepository(session)
        self.provider_factory = provider_factory or (
            lambda: create_default_provider(self.settings)
        )
        self.start_guard = start_guard or create_default_start_guard(self.settings)
        self.executor = OrchestrationExecutor(
            self.repository,
            self.provider_factory,
        )

    def start_job(self, job_id: UUID) -> None:
        job = self.repository.get_job(job_id)
        if job is None:
            raise LookupError(f"Job not found: {job_id}")

        self.repository.create_job_event(
            job_id,
            event_type=JobEventType.JOB_START_REQUESTED.value,
        )
        ensure_job_transition(job.status, JobStatus.RUNNING)

        lease = self.start_guard.acquire(job_id)
        if lease is None:
            self.repository.create_job_event(
                job_id,
                event_type=JobEventType.JOB_START_REJECTED_DUPLICATE.value,
            )
            raise DuplicateJobStartError(f"Job start already in progress: {job_id}")

        try:
            self.executor.start_job(job_id)
        finally:
            lease.release()

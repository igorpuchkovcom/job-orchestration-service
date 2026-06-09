from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.inference_metadata import (
    InvalidInferenceMetadataError,
    parse_inference_metadata,
)
from app.core.job_events import JobEventType
from app.core.job_lifecycle import JobStatus, ensure_job_transition
from app.model_registry.registry import resolve_model
from app.orchestration.pipeline.executor import OrchestrationExecutor
from app.persistence.repositories.job_repository import JobRepository
from app.providers.llm.openai_compatible_provider import OpenAICompatibleProvider
from app.providers.llm.openai_provider import LLMProvider, OpenAIProvider
from app.providers.llm.runtimes import LLMRuntime
from app.state.redis_state import RedisStartGuard

ProviderFactory = Callable[[], LLMProvider]


class InferenceConfigurationError(ValueError):
    pass


def _coerce_runtime(runtime_value: str | None) -> LLMRuntime | None:
    if runtime_value is None:
        return None
    try:
        return LLMRuntime(runtime_value)
    except ValueError as error:
        raise InferenceConfigurationError(
            f"Unsupported runtime value: {runtime_value}"
        ) from error


def create_default_provider(
    settings: Settings,
    *,
    runtime: LLMRuntime | None = None,
    model_id: str | None = None,
) -> LLMProvider:
    runtime_value, provider_model, local_base_url = _resolve_provider_selection(
        settings,
        runtime=runtime,
        model_id=model_id,
    )
    if runtime_value == LLMRuntime.OPENAI_API:
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=provider_model,
            timeout_seconds=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )

    if runtime_value == LLMRuntime.OPENAI_COMPATIBLE_LOCAL:
        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key or "local-dev-key",
            model=provider_model,
            base_url=local_base_url,
            timeout_seconds=settings.openai_timeout_seconds,
            max_retries=settings.openai_max_retries,
        )

    raise InferenceConfigurationError(
        "Runtime 'vllm_compatible_stub' is intentionally unsupported in this spike."
    )


def _resolve_provider_selection(
    settings: Settings,
    *,
    runtime: LLMRuntime | None,
    model_id: str | None,
) -> tuple[LLMRuntime, str, str]:
    provider_model = settings.openai_model
    runtime_value = runtime or LLMRuntime(settings.llm_runtime)
    base_url = settings.openai_base_url

    if model_id is not None:
        try:
            registry_entry = resolve_model(model_id)
        except ValueError as error:
            raise InferenceConfigurationError(str(error)) from error
        if runtime is not None and runtime != registry_entry.runtime:
            raise InferenceConfigurationError(
                f"Requested runtime '{runtime.value}' does not match model_id '{model_id}'."
            )
        runtime_value = registry_entry.runtime
        provider_model = registry_entry.provider_model
        base_url = registry_entry.base_url or base_url

    if runtime_value == LLMRuntime.OPENAI_COMPATIBLE_LOCAL and not base_url:
        raise InferenceConfigurationError(
            "openai_compatible_local runtime requires OPENAI_BASE_URL."
        )
    if runtime_value == LLMRuntime.VLLM_COMPATIBLE_STUB:
        raise InferenceConfigurationError(
            "Runtime 'vllm_compatible_stub' is intentionally unsupported in this spike."
        )

    return runtime_value, provider_model, base_url or ""


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
        self._provider_factory_injected = provider_factory is not None
        self.provider_factory = provider_factory or (
            lambda: create_default_provider(self.settings)
        )
        self.start_guard = start_guard or create_default_start_guard(self.settings)

    def start_job(self, job_id: UUID) -> None:
        job = self.repository.get_job(job_id)
        if job is None:
            raise LookupError(f"Job not found: {job_id}")

        self.repository.create_job_event(
            job_id,
            event_type=JobEventType.JOB_START_REQUESTED.value,
        )
        ensure_job_transition(job.status, JobStatus.RUNNING)

        try:
            inference_metadata = parse_inference_metadata(job.input_payload)
        except InvalidInferenceMetadataError as error:
            raise InferenceConfigurationError(str(error)) from error

        runtime = _coerce_runtime(inference_metadata.runtime)
        provider_factory = self.provider_factory
        inference_context = inference_metadata.as_payload()
        provider_factory_injected = getattr(self, "_provider_factory_injected", True)
        if not provider_factory_injected:
            model_id = inference_metadata.model_id
            _resolve_provider_selection(
                self.settings,
                runtime=runtime,
                model_id=model_id,
            )
            resolved_runtime_value = (
                runtime.value if runtime is not None else self.settings.llm_runtime
            )
            if model_id is not None and runtime is None:
                try:
                    resolved_runtime_value = resolve_model(model_id).runtime.value
                except ValueError:
                    # Keep the original model_id; provider construction will raise a clear error.
                    pass
            inference_context.setdefault("runtime", resolved_runtime_value)

            def _default_provider_factory() -> LLMProvider:
                return create_default_provider(
                    self.settings,
                    runtime=runtime,
                    model_id=model_id,
                )

            provider_factory = _default_provider_factory

        executor = OrchestrationExecutor(
            self.repository,
            provider_factory,
            inference_metadata=inference_context,
        )

        lease = self.start_guard.acquire(job_id)
        if lease is None:
            self.repository.create_job_event(
                job_id,
                event_type=JobEventType.JOB_START_REJECTED_DUPLICATE.value,
            )
            raise DuplicateJobStartError(f"Job start already in progress: {job_id}")

        try:
            executor.start_job(job_id)
        finally:
            lease.release()

import threading

from redis import Redis
from redis.exceptions import ConnectionError

from app.orchestration.services.orchestration_service import (
    DuplicateJobStartError,
    OrchestrationService,
)
from app.persistence.db import create_session_factory
from app.persistence.repositories.job_repository import JobRepository
from app.providers.llm.openai_provider import LLMGenerationResult
from app.state.redis_state import RedisStartGuard


class InMemoryRedisClient:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: set[str] = set()

    def set(
        self,
        name: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        assert value == "1"
        assert ex == 30
        assert nx is True

        with self._lock:
            if name in self._keys:
                return None
            self._keys.add(name)
            return True

    def delete(self, *names: str) -> int:
        deleted = 0
        with self._lock:
            for name in names:
                if name in self._keys:
                    self._keys.remove(name)
                    deleted += 1
        return deleted


class FailingRedisClient:
    def set(
        self,
        name: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        raise ConnectionError("redis unavailable")

    def delete(self, *names: str) -> int:
        raise ConnectionError("redis unavailable")


class BlockingProvider:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.allow_finish = threading.Event()
        self.calls = 0

    def generate_text(self, prompt: str) -> LLMGenerationResult:
        assert prompt == "demo"
        self.calls += 1
        self.started.set()
        if not self.allow_finish.wait(timeout=5):
            raise AssertionError("BlockingProvider did not receive release signal.")
        return LLMGenerationResult(
            provider="openai",
            model="test-model",
            content="provider-backed content",
        )


class StaticProvider:
    def generate_text(self, prompt: str) -> LLMGenerationResult:
        assert prompt == "demo"
        return LLMGenerationResult(
            provider="openai",
            model="test-model",
            content="provider-backed content",
        )


def test_orchestration_service_rejects_duplicate_in_flight_start(migrated_engine) -> None:
    session_factory = create_session_factory(migrated_engine)
    start_guard = RedisStartGuard(
        redis_url=None,
        ttl_seconds=30,
        client=InMemoryRedisClient(),
    )
    provider = BlockingProvider()

    with session_factory() as session:
        repository = JobRepository(session)
        job = repository.create_job(status="pending", input_payload={"prompt": "demo"})
        job_id = job.id
        session.commit()

    thread_errors: list[BaseException] = []

    def run_first_start() -> None:
        try:
            with session_factory() as session:
                OrchestrationService(
                    session,
                    provider_factory=lambda: provider,
                    start_guard=start_guard,
                ).start_job(job_id)
                session.commit()
        except BaseException as error:  # pragma: no cover - assertion path only
            thread_errors.append(error)

    first_thread = threading.Thread(target=run_first_start)
    first_thread.start()

    assert provider.started.wait(timeout=5)

    with session_factory() as session:
        try:
            OrchestrationService(
                session,
                provider_factory=lambda: provider,
                start_guard=start_guard,
            ).start_job(job_id)
        except DuplicateJobStartError as error:
            assert "already in progress" in str(error)
        else:
            raise AssertionError("Expected duplicate in-flight start to be rejected.")

    provider.allow_finish.set()
    first_thread.join(timeout=5)
    assert not first_thread.is_alive()
    assert thread_errors == []
    assert provider.calls == 1

    with session_factory() as session:
        reloaded_job = JobRepository(session).get_job(job_id)

        assert reloaded_job is not None
        assert reloaded_job.status == "completed"
        assert len(reloaded_job.steps) == 1
        assert reloaded_job.steps[0].step_key == "llm_generate_text"


def test_orchestration_service_fails_open_when_redis_is_unavailable(migrated_engine) -> None:
    session_factory = create_session_factory(migrated_engine)
    start_guard = RedisStartGuard(
        redis_url=None,
        ttl_seconds=30,
        client=FailingRedisClient(),
    )

    with session_factory() as session:
        repository = JobRepository(session)
        job = repository.create_job(status="pending", input_payload={"prompt": "demo"})
        job_id = job.id

        OrchestrationService(
            session,
            provider_factory=lambda: StaticProvider(),
            start_guard=start_guard,
        ).start_job(job_id)
        session.commit()

    with session_factory() as session:
        reloaded_job = JobRepository(session).get_job(job_id)

        assert reloaded_job is not None
        assert reloaded_job.status == "completed"
        assert len(reloaded_job.steps) == 1
        assert reloaded_job.steps[0].step_key == "llm_generate_text"


def test_orchestration_service_uses_real_redis_guard_for_duplicate_start(
    migrated_engine,
    redis_url,
    clean_redis: Redis,
) -> None:
    session_factory = create_session_factory(migrated_engine)
    provider = BlockingProvider()
    start_guard = RedisStartGuard(redis_url=redis_url, ttl_seconds=30)

    with session_factory() as session:
        repository = JobRepository(session)
        job = repository.create_job(status="pending", input_payload={"prompt": "demo"})
        job_id = job.id
        session.commit()

    thread_errors: list[BaseException] = []

    def run_first_start() -> None:
        try:
            with session_factory() as session:
                OrchestrationService(
                    session,
                    provider_factory=lambda: provider,
                    start_guard=start_guard,
                ).start_job(job_id)
                session.commit()
        except BaseException as error:  # pragma: no cover - assertion path only
            thread_errors.append(error)

    first_thread = threading.Thread(target=run_first_start)
    first_thread.start()

    assert provider.started.wait(timeout=5)
    assert clean_redis.exists(RedisStartGuard.build_key(job_id)) == 1

    with session_factory() as session:
        try:
            OrchestrationService(
                session,
                provider_factory=lambda: provider,
                start_guard=start_guard,
            ).start_job(job_id)
        except DuplicateJobStartError:
            pass
        else:
            raise AssertionError("Expected duplicate in-flight start to be rejected.")

    provider.allow_finish.set()
    first_thread.join(timeout=5)
    assert not first_thread.is_alive()
    assert thread_errors == []
    assert clean_redis.exists(RedisStartGuard.build_key(job_id)) == 0

import threading

from fastapi.testclient import TestClient

from app.main import create_app
from app.orchestration.services.orchestration_service import OrchestrationService
from app.persistence.db import create_session_factory
from app.persistence.repositories.job_repository import JobRepository
from app.providers.llm.openai_provider import LLMGenerationResult
from app.state.redis_state import RedisStartGuard


def test_start_job_returns_orchestration_owned_completed_flow(
    migrated_engine,
    database_url,
    monkeypatch,
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
    response = client.post(f"/jobs/{job_id}/start")

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
    assert body["result_summary"] == {
        "provider": "openai",
        "model": "test-model",
        "content": "provider-backed content",
    }


def test_start_job_returns_failed_state_for_provider_error(
    migrated_engine,
    database_url,
    monkeypatch,
) -> None:
    session_factory = create_session_factory(migrated_engine)

    monkeypatch.setattr(
        OrchestrationService,
        "__init__",
        _fake_service_init_failure,
    )

    with session_factory() as session:
        job = JobRepository(session).create_job(status="pending", input_payload={"prompt": "demo"})
        job_id = job.id
        session.commit()

    client = TestClient(create_app())
    response = client.post(f"/jobs/{job_id}/start")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(job_id)
    assert body["status"] == "failed"
    assert len(body["steps"]) == 1
    assert body["steps"][0]["step_key"] == "llm_generate_text"
    assert body["steps"][0]["status"] == "failed"
    assert body["steps"][0]["output_payload"] is None
    assert body["steps"][0]["error_payload"] == {
        "type": "RuntimeError",
        "message": "provider unavailable",
    }
    assert body["result_summary"] is None


def test_start_job_returns_409_for_duplicate_in_flight_start(
    migrated_engine,
    database_url,
    monkeypatch,
) -> None:
    session_factory = create_session_factory(migrated_engine)
    provider = _BlockingProvider()
    start_guard = RedisStartGuard(
        redis_url=None,
        ttl_seconds=30,
        client=_InMemoryRedisClient(),
    )

    monkeypatch.setattr(
        OrchestrationService,
        "__init__",
        lambda self, session: _fake_service_init_with_dependencies(
            self,
            session,
            provider_factory=lambda: provider,
            start_guard=start_guard,
        ),
    )

    with session_factory() as session:
        job = JobRepository(session).create_job(status="pending", input_payload={"prompt": "demo"})
        job_id = job.id
        session.commit()

    app = create_app()
    thread_errors: list[BaseException] = []
    responses: dict[str, object] = {}

    def run_first_start() -> None:
        try:
            with TestClient(app) as client:
                responses["first"] = client.post(f"/jobs/{job_id}/start")
        except BaseException as error:  # pragma: no cover - assertion path only
            thread_errors.append(error)

    first_thread = threading.Thread(target=run_first_start)
    first_thread.start()

    assert provider.started.wait(timeout=5)

    with TestClient(app) as client:
        duplicate_response = client.post(f"/jobs/{job_id}/start")

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {"detail": "Job start is already in progress."}

    provider.allow_finish.set()
    first_thread.join(timeout=5)
    assert not first_thread.is_alive()
    assert thread_errors == []

    first_response = responses["first"]
    assert isinstance(first_response, type(duplicate_response))
    assert first_response.status_code == 200


def test_repeated_start_after_completion_returns_existing_status_conflict(
    migrated_engine,
    database_url,
    monkeypatch,
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

    first_response = client.post(f"/jobs/{job_id}/start")
    second_response = client.post(f"/jobs/{job_id}/start")

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Job cannot be started from its current status."}


def test_start_job_returns_409_for_invalid_transition(migrated_engine, database_url) -> None:
    session_factory = create_session_factory(migrated_engine)

    with session_factory() as session:
        job = JobRepository(session).create_job(status="running", input_payload={"prompt": "demo"})
        job_id = job.id
        session.commit()

    client = TestClient(create_app())
    response = client.post(f"/jobs/{job_id}/start")

    assert response.status_code == 409
    assert response.json() == {"detail": "Job cannot be started from its current status."}


def test_start_job_returns_404_for_unknown_id(migrated_engine, database_url) -> None:
    assert migrated_engine is not None
    client = TestClient(create_app())
    response = client.post("/jobs/00000000-0000-0000-0000-000000000000/start")

    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found."}


def _fake_service_init_success(self, session) -> None:
    _fake_service_init_with_dependencies(
        self,
        session,
        provider_factory=lambda: _FakeProvider(
            result=LLMGenerationResult(
                provider="openai",
                model="test-model",
                content="provider-backed content",
            )
        ),
        start_guard=RedisStartGuard(redis_url=None, ttl_seconds=30),
    )


def _fake_service_init_failure(self, session) -> None:
    _fake_service_init_with_dependencies(
        self,
        session,
        provider_factory=lambda: _FakeProvider(error=RuntimeError("provider unavailable")),
        start_guard=RedisStartGuard(redis_url=None, ttl_seconds=30),
    )


def _fake_service_init_with_dependencies(
    self,
    session,
    *,
    provider_factory,
    start_guard,
) -> None:
    self.repository = JobRepository(session)
    self.settings = None
    self.provider_factory = provider_factory
    self.start_guard = start_guard
    from app.orchestration.pipeline.executor import OrchestrationExecutor

    self.executor = OrchestrationExecutor(self.repository, self.provider_factory)


class _InMemoryRedisClient:
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


class _BlockingProvider:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.allow_finish = threading.Event()

    def generate_text(self, prompt: str) -> LLMGenerationResult:
        assert prompt == "demo"
        self.started.set()
        if not self.allow_finish.wait(timeout=5):
            raise AssertionError("Blocking provider did not receive release signal.")
        return LLMGenerationResult(
            provider="openai",
            model="test-model",
            content="provider-backed content",
        )

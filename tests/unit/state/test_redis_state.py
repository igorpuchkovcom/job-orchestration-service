from uuid import uuid4

from redis.exceptions import ConnectionError

from app.state.redis_state import RedisStartGuard


class RecordingRedisClient:
    def __init__(self, *, acquire_result: bool | None = True) -> None:
        self.acquire_result = acquire_result
        self.set_calls: list[tuple[str, str, int | None, bool]] = []
        self.delete_calls: list[str] = []
        self.eval_calls: list[tuple[str, int, str, str]] = []

    def set(
        self,
        name: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None:
        self.set_calls.append((name, value, ex, nx))
        return self.acquire_result

    def delete(self, *names: str) -> int:
        self.delete_calls.extend(names)
        return len(names)

    def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        self.eval_calls.append((script, numkeys, key, token))
        return 1


class FailingSetRedisClient:
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
        return len(names)


class FailingEvalRedisClient(RecordingRedisClient):
    def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        raise ConnectionError("redis unavailable")


def test_start_guard_acquires_key_with_bounded_ttl_and_releases_it() -> None:
    job_id = uuid4()
    client = RecordingRedisClient()
    guard = RedisStartGuard(redis_url=None, ttl_seconds=30, client=client)

    lease = guard.acquire(job_id)

    assert lease is not None
    assert lease.key == f"job-service:job:{job_id}:start-guard"
    assert len(client.set_calls) == 1
    key, token, ex, nx = client.set_calls[0]
    assert key == lease.key
    assert token == lease.token
    assert ex == 30
    assert nx is True

    lease.release()

    assert client.delete_calls == []
    assert len(client.eval_calls) == 1
    _, numkeys, key, token = client.eval_calls[0]
    assert numkeys == 1
    assert key == lease.key
    assert token == lease.token


def test_start_guard_returns_none_when_duplicate_start_is_in_flight() -> None:
    client = RecordingRedisClient(acquire_result=None)
    guard = RedisStartGuard(redis_url=None, ttl_seconds=30, client=client)

    lease = guard.acquire(uuid4())

    assert lease is None


def test_start_guard_fails_open_when_redis_is_unavailable() -> None:
    guard = RedisStartGuard(
        redis_url=None,
        ttl_seconds=30,
        client=FailingSetRedisClient(),
    )

    lease = guard.acquire(uuid4())

    assert lease is not None
    assert lease.client is None


def test_start_guard_release_is_best_effort_when_redis_errors() -> None:
    guard = RedisStartGuard(
        redis_url=None,
        ttl_seconds=30,
        client=FailingEvalRedisClient(),
    )

    lease = guard.acquire(uuid4())

    assert lease is not None
    lease.release()


def test_start_guard_rejects_non_positive_ttl() -> None:
    try:
        RedisStartGuard(redis_url=None, ttl_seconds=0)
    except ValueError as error:
        assert "TTL" in str(error)
    else:
        raise AssertionError("Expected ValueError for invalid TTL.")

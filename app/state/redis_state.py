from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from redis import Redis
from redis.exceptions import RedisError


class SupportsRedisStartGuard(Protocol):
    def set(
        self,
        name: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool | None: ...

    def delete(self, *names: str) -> int: ...


@dataclass(frozen=True)
class StartGuardLease:
    key: str
    client: SupportsRedisStartGuard | None = None

    def release(self) -> None:
        if self.client is None:
            return

        try:
            self.client.delete(self.key)
        except RedisError:
            return


class RedisStartGuard:
    def __init__(
        self,
        *,
        redis_url: str | None,
        ttl_seconds: int,
        client: SupportsRedisStartGuard | None = None,
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError("Redis start-guard TTL must be at least 1 second.")

        self.ttl_seconds = ttl_seconds
        self.client = client if client is not None else self._build_client(redis_url)

    def acquire(self, job_id: UUID) -> StartGuardLease | None:
        key = self.build_key(job_id)
        if self.client is None:
            # Missing Redis config should not block the synchronous request path.
            return StartGuardLease(key=key)

        try:
            acquired = self.client.set(key, "1", ex=self.ttl_seconds, nx=True)
        except RedisError:
            return StartGuardLease(key=key)

        if not acquired:
            return None

        return StartGuardLease(key=key, client=self.client)

    @staticmethod
    def build_key(job_id: UUID) -> str:
        return f"job-service:job:{job_id}:start-guard"

    @staticmethod
    def _build_client(redis_url: str | None) -> Redis | None:
        if not redis_url:
            return None
        return Redis.from_url(redis_url)

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.manifests.builder import build_result_summary


@dataclass
class FakeJobStep:
    step_key: str
    status: str
    output_payload: dict[str, Any] | None = None


@dataclass
class FakeJob:
    status: str
    steps: list[FakeJobStep] = field(default_factory=list)
    id: object = field(default_factory=uuid4)


def test_build_result_summary_returns_small_projection_for_completed_job() -> None:
    job = FakeJob(
        status="completed",
        steps=[
            FakeJobStep(
                step_key="llm_generate_text",
                status="completed",
                output_payload={
                    "content": "provider-backed content",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "usage": {"total_tokens": 42},
                },
            )
        ],
    )

    assert build_result_summary(job) == {
        "content": "provider-backed content",
        "provider": "openai",
        "model": "gpt-4o-mini",
    }


def test_build_result_summary_returns_none_for_failed_job() -> None:
    job = FakeJob(
        status="failed",
        steps=[
            FakeJobStep(
                step_key="llm_generate_text",
                status="failed",
                output_payload=None,
            )
        ],
    )

    assert build_result_summary(job) is None


def test_build_result_summary_returns_none_for_running_or_pending_jobs() -> None:
    running_job = FakeJob(
        status="running",
        steps=[
            FakeJobStep(
                step_key="llm_generate_text",
                status="completed",
                output_payload={
                    "content": "provider-backed content",
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                },
            )
        ],
    )
    pending_job = FakeJob(status="pending", steps=[])

    assert build_result_summary(running_job) is None
    assert build_result_summary(pending_job) is None


def test_build_result_summary_returns_none_when_completed_output_is_missing_fields() -> None:
    job = FakeJob(
        status="completed",
        steps=[
            FakeJobStep(
                step_key="llm_generate_text",
                status="completed",
                output_payload={
                    "content": "provider-backed content",
                    "provider": "openai",
                },
            )
        ],
    )

    assert build_result_summary(job) is None


def test_build_result_summary_ignores_non_result_steps() -> None:
    job = FakeJob(
        status="completed",
        steps=[
            FakeJobStep(
                step_key="prepare",
                status="completed",
                output_payload={"content": "not final"},
            )
        ],
    )

    assert build_result_summary(job) is None

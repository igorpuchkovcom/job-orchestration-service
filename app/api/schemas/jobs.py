from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.manifests.builder import build_result_summary
from app.persistence.models import Job


class JobCreateRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


class JobStepResponse(BaseModel):
    id: UUID
    step_key: str
    step_index: int
    status: str
    output_payload: dict[str, Any] | None = None
    error_payload: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: UUID
    status: str
    input_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    steps: list[JobStepResponse]
    result_summary: dict[str, Any] | None = None


def job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        status=job.status,
        input_payload=job.input_payload,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        steps=[JobStepResponse.model_validate(step) for step in job.steps],
        result_summary=build_result_summary(job),
    )

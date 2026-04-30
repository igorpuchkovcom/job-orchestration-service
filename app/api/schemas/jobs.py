from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.job_lifecycle import (
    JobStatus,
    JobStepStatus,
    coerce_job_status,
    coerce_job_step_status,
)
from app.manifests.builder import build_result_summary
from app.persistence.models import Job


class JobCreateRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


class JobStepResponse(BaseModel):
    id: UUID
    step_key: str
    step_index: int
    status: JobStepStatus
    output_payload: dict[str, Any] | None = None
    error_payload: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: UUID
    status: JobStatus
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
        status=coerce_job_status(job.status),
        input_payload=job.input_payload,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        steps=[
            JobStepResponse.model_validate(
                {
                    "id": step.id,
                    "step_key": step.step_key,
                    "step_index": step.step_index,
                    "status": coerce_job_step_status(step.status),
                    "output_payload": step.output_payload,
                    "error_payload": step.error_payload,
                    "created_at": step.created_at,
                    "updated_at": step.updated_at,
                }
            )
            for step in job.steps
        ],
        result_summary=build_result_summary(job),
    )

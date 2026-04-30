from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.job_lifecycle import (
    JobStatus,
    JobStepStatus,
    coerce_job_status,
    ensure_job_transition,
    serialize_job_status,
    serialize_job_step_status,
)
from app.persistence.models import Job, JobEvent, JobStep


@dataclass(frozen=True)
class JobStepCreate:
    step_key: str
    step_index: int
    status: JobStepStatus | str
    output_payload: dict[str, Any] | None = None
    error_payload: dict[str, Any] | None = None


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(
        self,
        *,
        status: JobStatus | str,
        input_payload: dict[str, Any],
        steps: list[JobStepCreate] | None = None,
    ) -> Job:
        job = Job(status=serialize_job_status(status), input_payload=input_payload)
        for step in steps or []:
            job.steps.append(
                JobStep(
                    step_key=step.step_key,
                    step_index=step.step_index,
                    status=serialize_job_step_status(step.status),
                    output_payload=step.output_payload,
                    error_payload=step.error_payload,
                )
            )

        self.session.add(job)
        self.session.flush()
        return job

    def get_job(self, job_id: UUID) -> Job | None:
        statement = (
            select(Job)
            .options(selectinload(Job.steps), selectinload(Job.events))
            .where(Job.id == job_id)
        )
        return self.session.scalar(statement)

    def update_job_status(
        self,
        job_id: UUID,
        *,
        status: JobStatus | str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> Job:
        job = self._require_job(job_id)
        current_status = coerce_job_status(job.status)
        target_status = coerce_job_status(status)
        if current_status != target_status:
            ensure_job_transition(current_status, target_status)
        job.status = target_status.value
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at

        self.session.flush()
        return job

    def update_job_step(
        self,
        step_id: UUID,
        *,
        status: JobStepStatus | str,
        output_payload: dict[str, Any] | None = None,
        error_payload: dict[str, Any] | None = None,
    ) -> JobStep:
        job_step = self._require_job_step(step_id)
        job_step.status = serialize_job_step_status(status)
        job_step.output_payload = output_payload
        job_step.error_payload = error_payload

        self.session.flush()
        return job_step

    def create_job_step(
        self,
        job_id: UUID,
        *,
        step_key: str,
        step_index: int,
        status: JobStepStatus | str,
        output_payload: dict[str, Any] | None = None,
        error_payload: dict[str, Any] | None = None,
    ) -> JobStep:
        job = self._require_job(job_id)
        job_step = JobStep(
            job_id=job.id,
            step_key=step_key,
            step_index=step_index,
            status=serialize_job_step_status(status),
            output_payload=output_payload,
            error_payload=error_payload,
        )
        self.session.add(job_step)
        self.session.flush()
        return job_step

    def create_job_event(
        self,
        job_id: UUID,
        *,
        event_type: str,
        event_payload: dict[str, Any] | None = None,
    ) -> JobEvent:
        self._require_job(job_id)
        job_event = JobEvent(
            job_id=job_id,
            event_type=event_type,
            event_payload=event_payload,
        )
        self.session.add(job_event)
        self.session.flush()
        return job_event

    def _require_job(self, job_id: UUID) -> Job:
        job = self.get_job(job_id)
        if job is None:
            raise LookupError(f"Job not found: {job_id}")
        return job

    def _require_job_step(self, step_id: UUID) -> JobStep:
        statement = select(JobStep).where(JobStep.id == step_id)
        job_step = self.session.scalar(statement)
        if job_step is None:
            raise LookupError(f"JobStep not found: {step_id}")
        return job_step

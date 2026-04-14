from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.persistence.models import Job, JobStep


@dataclass(frozen=True)
class JobStepCreate:
    step_key: str
    step_index: int
    status: str
    output_payload: dict[str, Any] | None = None
    error_payload: dict[str, Any] | None = None


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_job(
        self,
        *,
        status: str,
        input_payload: dict[str, Any],
        steps: list[JobStepCreate] | None = None,
    ) -> Job:
        job = Job(status=status, input_payload=input_payload)
        for step in steps or []:
            job.steps.append(
                JobStep(
                    step_key=step.step_key,
                    step_index=step.step_index,
                    status=step.status,
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
            .options(selectinload(Job.steps))
            .where(Job.id == job_id)
        )
        return self.session.scalar(statement)

    def update_job_status(
        self,
        job_id: UUID,
        *,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> Job:
        job = self._require_job(job_id)
        job.status = status
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
        status: str,
        output_payload: dict[str, Any] | None = None,
        error_payload: dict[str, Any] | None = None,
    ) -> JobStep:
        job_step = self._require_job_step(step_id)
        job_step.status = status
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
        status: str,
        output_payload: dict[str, Any] | None = None,
        error_payload: dict[str, Any] | None = None,
    ) -> JobStep:
        job = self._require_job(job_id)
        job_step = JobStep(
            job_id=job.id,
            step_key=step_key,
            step_index=step_index,
            status=status,
            output_payload=output_payload,
            error_payload=error_payload,
        )
        self.session.add(job_step)
        self.session.flush()
        return job_step

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

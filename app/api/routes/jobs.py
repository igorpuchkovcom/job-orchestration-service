from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.schemas.jobs import JobCreateRequest, JobResponse, job_to_response
from app.orchestration.services.orchestration_service import (
    DuplicateJobStartError,
    OrchestrationService,
)
from app.persistence.db import session_scope
from app.persistence.repositories.job_repository import JobRepository

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(request: JobCreateRequest) -> JobResponse:
    with session_scope() as session:
        repository = JobRepository(session)
        job = repository.create_job(status="pending", input_payload=request.input)
        job = repository.get_job(job.id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Created job could not be reloaded.",
            )
        return job_to_response(job)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID) -> JobResponse:
    with session_scope() as session:
        job = JobRepository(session).get_job(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return job_to_response(job)


@router.post("/{job_id}/start", response_model=JobResponse)
def start_job(job_id: UUID) -> JobResponse:
    with session_scope() as session:
        repository = JobRepository(session)
        try:
            OrchestrationService(session).start_job(job_id)
        except LookupError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found.",
            ) from error
        except DuplicateJobStartError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Job start is already in progress.",
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Job cannot be started from its current status.",
            ) from error

        session.expire_all()
        started_job = repository.get_job(job_id)
        if started_job is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Started job could not be reloaded.",
            )
        return job_to_response(started_job)

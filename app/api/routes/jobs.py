from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth import DemoRole, require_roles
from app.api.errors import make_api_error
from app.api.schemas.jobs import JobCreateRequest, JobResponse, job_to_response
from app.core.job_events import JobEventType
from app.core.job_lifecycle import JobStatus
from app.orchestration.services.orchestration_service import (
    DuplicateJobStartError,
    OrchestrationService,
)
from app.persistence.db import session_scope
from app.persistence.repositories.job_repository import JobRepository

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(DemoRole.OPERATOR, DemoRole.ADMIN))],
)
def create_job(request: JobCreateRequest) -> JobResponse:
    with session_scope() as session:
        repository = JobRepository(session)
        job = repository.create_job(status=JobStatus.PENDING, input_payload=request.input)
        repository.create_job_event(
            job.id,
            event_type=JobEventType.JOB_CREATED.value,
        )
        job = repository.get_job(job.id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=make_api_error(
                    code="job_reload_failed",
                    message="Created job could not be reloaded.",
                ),
            )
        return job_to_response(job)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    dependencies=[Depends(require_roles(DemoRole.VIEWER, DemoRole.OPERATOR, DemoRole.ADMIN))],
)
def get_job(job_id: UUID) -> JobResponse:
    with session_scope() as session:
        job = JobRepository(session).get_job(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=make_api_error(code="job_not_found", message="Job not found."),
            )
        return job_to_response(job)


@router.post(
    "/{job_id}/start",
    response_model=JobResponse,
    dependencies=[Depends(require_roles(DemoRole.OPERATOR, DemoRole.ADMIN))],
)
def start_job(job_id: UUID) -> JobResponse:
    with session_scope() as session:
        repository = JobRepository(session)
        try:
            OrchestrationService(session).start_job(job_id)
        except LookupError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=make_api_error(code="job_not_found", message="Job not found."),
            ) from error
        except DuplicateJobStartError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=make_api_error(
                    code="duplicate_job_start",
                    message="Job start is already in progress.",
                ),
            ) from error
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=make_api_error(
                    code="invalid_job_transition",
                    message=str(error),
                ),
            ) from error

        session.expire_all()
        started_job = repository.get_job(job_id)
        if started_job is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=make_api_error(
                    code="job_reload_failed",
                    message="Started job could not be reloaded.",
                ),
            )
        return job_to_response(started_job)

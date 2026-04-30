from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


JOB_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {JobStatus.RUNNING},
    JobStatus.RUNNING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
}


def coerce_job_status(value: JobStatus | str) -> JobStatus:
    if isinstance(value, JobStatus):
        return value
    try:
        return JobStatus(value)
    except ValueError as error:
        raise ValueError(f"Unknown job status: {value}") from error


def coerce_job_step_status(value: JobStepStatus | str) -> JobStepStatus:
    if isinstance(value, JobStepStatus):
        return value
    try:
        return JobStepStatus(value)
    except ValueError as error:
        raise ValueError(f"Unknown job step status: {value}") from error


def ensure_job_transition(current: JobStatus | str, target: JobStatus | str) -> None:
    current_status = coerce_job_status(current)
    target_status = coerce_job_status(target)

    allowed_targets = JOB_TRANSITIONS[current_status]
    if target_status not in allowed_targets:
        raise ValueError(
            f"Invalid job status transition: {current_status.value} -> {target_status.value}"
        )


def serialize_job_status(value: JobStatus | str) -> str:
    return coerce_job_status(value).value


def serialize_job_step_status(value: JobStepStatus | str) -> str:
    return coerce_job_step_status(value).value

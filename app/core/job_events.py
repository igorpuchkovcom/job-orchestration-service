from enum import Enum


class JobEventType(str, Enum):
    JOB_CREATED = "job_created"
    JOB_START_REQUESTED = "job_start_requested"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_START_REJECTED_DUPLICATE = "job_start_rejected_duplicate"

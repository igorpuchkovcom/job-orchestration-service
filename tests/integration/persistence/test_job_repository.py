from datetime import UTC, datetime

from app.persistence.db import create_session_factory
from app.persistence.repositories import JobRepository, JobStepCreate


def test_job_repository_creates_and_loads_job_with_ordered_steps(migrated_engine) -> None:
    session_factory = create_session_factory(migrated_engine)

    with session_factory() as session:
        repository = JobRepository(session)
        job = repository.create_job(
            status="pending",
            input_payload={"request": "demo"},
            steps=[
                JobStepCreate(step_key="plan", step_index=1, status="pending"),
                JobStepCreate(step_key="execute", step_index=2, status="pending"),
            ],
        )
        job_id = job.id
        session.commit()

    with session_factory() as session:
        loaded_job = JobRepository(session).get_job(job_id)

        assert loaded_job is not None
        assert loaded_job.status == "pending"
        assert loaded_job.input_payload == {"request": "demo"}
        assert [step.step_key for step in loaded_job.steps] == ["plan", "execute"]
        assert [step.step_index for step in loaded_job.steps] == [1, 2]


def test_job_repository_updates_job_and_step_state(migrated_engine) -> None:
    session_factory = create_session_factory(migrated_engine)
    started_at = datetime.now(UTC)
    completed_at = datetime.now(UTC)

    with session_factory() as session:
        repository = JobRepository(session)
        job = repository.create_job(
            status="pending",
            input_payload={"request": "demo"},
            steps=[JobStepCreate(step_key="execute", step_index=1, status="pending")],
        )
        job_id = job.id
        step_id = job.steps[0].id
        session.commit()

    with session_factory() as session:
        repository = JobRepository(session)
        repository.update_job_status(job_id, status="running", started_at=started_at)
        repository.update_job_step(
            step_id,
            status="completed",
            output_payload={"result": "ok"},
            error_payload=None,
        )
        repository.update_job_status(job_id, status="completed", completed_at=completed_at)
        session.commit()

    with session_factory() as session:
        loaded_job = JobRepository(session).get_job(job_id)

        assert loaded_job is not None
        assert loaded_job.status == "completed"
        assert loaded_job.started_at == started_at
        assert loaded_job.completed_at == completed_at
        assert loaded_job.steps[0].status == "completed"
        assert loaded_job.steps[0].output_payload == {"result": "ok"}
        assert loaded_job.steps[0].error_payload is None


def test_job_repository_appends_events_without_mutation(migrated_engine) -> None:
    session_factory = create_session_factory(migrated_engine)

    with session_factory() as session:
        repository = JobRepository(session)
        job = repository.create_job(
            status="pending",
            input_payload={"request": "demo"},
        )
        job_id = job.id

        repository.create_job_event(job_id, event_type="job_created")
        repository.create_job_event(
            job_id,
            event_type="job_started",
            event_payload={"source": "integration-test"},
        )
        session.commit()

    with session_factory() as session:
        loaded_job = JobRepository(session).get_job(job_id)
        assert loaded_job is not None
        assert [event.event_type for event in loaded_job.events] == ["job_created", "job_started"]
        assert loaded_job.events[0].event_payload is None
        assert loaded_job.events[1].event_payload == {"source": "integration-test"}

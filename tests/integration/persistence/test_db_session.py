from sqlalchemy import inspect, select

from app.persistence.db import Base, create_session_factory
from app.persistence.models import Job, JobStep


def test_db_session_can_execute_simple_query(database_engine) -> None:
    session_factory = create_session_factory(database_engine)

    with session_factory() as session:
        assert session.execute(select(1)).scalar_one() == 1


def test_metadata_contains_only_planned_models() -> None:
    # Importing the models registers them with the declarative metadata.
    assert Job.__tablename__ == "jobs"
    assert JobStep.__tablename__ == "job_steps"
    assert set(Base.metadata.tables) == {"jobs", "job_steps"}


def test_model_mappings_are_valid() -> None:
    job_steps_table = Base.metadata.tables["job_steps"]

    assert "job_id" in job_steps_table.columns
    assert inspect(Job).relationships["steps"].mapper.class_ is JobStep

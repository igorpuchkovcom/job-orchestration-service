from sqlalchemy import inspect

from alembic import command


def test_initial_migration_creates_only_expected_tables(
    clean_database_engine,
    alembic_config,
) -> None:
    command.upgrade(alembic_config, "head")

    inspector = inspect(clean_database_engine)
    assert set(inspector.get_table_names()) == {
        "alembic_version",
        "job_events",
        "job_steps",
        "jobs",
    }

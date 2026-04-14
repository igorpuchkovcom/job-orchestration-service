from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

metadata = MetaData()
SESSION_FACTORY_KWARGS = {
    "autoflush": False,
    "expire_on_commit": False,
}


class Base(DeclarativeBase):
    metadata = metadata


def create_engine_from_url(database_url: str) -> Engine:
    return create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
    )


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine_from_url(settings.database_url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), **SESSION_FACTORY_KWARGS)


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    if engine is None:
        return get_session_factory()

    return sessionmaker(bind=engine, **SESSION_FACTORY_KWARGS)


def reset_db_state() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()

    get_session_factory.cache_clear()
    get_engine.cache_clear()


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    session = create_session_factory(engine=engine)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

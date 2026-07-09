from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _alembic_config() -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _schema_at_head():
    """Ensure the schema is at head before the test session starts."""
    command.upgrade(_alembic_config(), "head")
    yield


@pytest.fixture(scope="session")
def engine():
    return create_engine(get_settings().database_url, future=True)


@pytest.fixture()
def db_session(engine):
    """One connection + outer transaction per test, rolled back at teardown.

    Code under test may freely call session.commit(); a SAVEPOINT is
    restarted after each commit so the outer transaction (and therefore the
    final rollback) still discards everything the test wrote.
    """
    connection = engine.connect()
    outer_trans = connection.begin()
    Session = sessionmaker(bind=connection, future=True)
    session = Session()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_trans.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    from tests.db import factories

    for factory_cls in factories.ALL_FACTORIES:
        factory_cls._meta.sqlalchemy_session = db_session
        factory_cls._meta.sqlalchemy_session_persistence = "flush"
    yield

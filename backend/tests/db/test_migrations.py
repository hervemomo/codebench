"""alembic upgrade head -> downgrade base -> upgrade head, on the live dev DB.

Always ends back at head (in a finally-block) so this test's own cleanup
never leaves other tests — which assume an up-to-date schema — broken,
regardless of test execution order within the session.
"""

from alembic import command
from sqlalchemy import inspect

from tests.db.conftest import _alembic_config

_ALL_TABLES = {
    "organizations", "users", "projects", "questions", "datasets",
    "responses", "coding_runs", "code_assignments", "export_artifacts",
}


def test_upgrade_head_then_downgrade_base_succeeds(engine):
    cfg = _alembic_config()

    try:
        command.upgrade(cfg, "head")
        inspector = inspect(engine)
        assert _ALL_TABLES.issubset(set(inspector.get_table_names()))

        command.downgrade(cfg, "base")
        inspector = inspect(engine)
        remaining = set(inspector.get_table_names())
        assert not _ALL_TABLES & remaining
    finally:
        command.upgrade(cfg, "head")

    inspector = inspect(engine)
    assert _ALL_TABLES.issubset(set(inspector.get_table_names()))


def test_downgrade_then_upgrade_is_repeatable(engine):
    """Regression test: native Postgres ENUM types outlive DROP TABLE, so a
    naive downgrade breaks the next upgrade with "type already exists" unless
    the migration explicitly drops them (see 0001_initial.py's downgrade())."""
    cfg = _alembic_config()

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")  # would raise here if enum types weren't cleaned up

    inspector = inspect(engine)
    assert _ALL_TABLES.issubset(set(inspector.get_table_names()))

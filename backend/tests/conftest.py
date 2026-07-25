"""Shared test fixtures: a fresh in-memory SQLite database per test, and
helpers for loading the recorded API responses under tests/fixtures/api/.

Why a fresh database per test rather than one shared connection: tests must
never depend on execution order or leak state into each other. An
in-memory SQLite database is fast enough (microseconds) that "fresh per
test" costs nothing, and it's what makes the whole suite runnable
offline and deterministic (Rule 5).
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import enable_sqlite_foreign_keys
from app.models import Base

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def db_session():
    """A fresh, isolated in-memory SQLite database, tables created straight
    from the models' metadata (not via Alembic — that's what makes this
    fast; Alembic migrations are for real deployments, not test setup)."""
    engine = create_engine("sqlite:///:memory:")
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def load_fixture(*path_parts: str) -> str:
    """Read a fixture file's raw text: load_fixture("api", "chesscom_month.json")."""
    return FIXTURES_DIR.joinpath(*path_parts).read_text()


def load_json_fixture(*path_parts: str):
    """Read and parse a JSON fixture file."""
    return json.loads(load_fixture(*path_parts))

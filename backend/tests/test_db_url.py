"""Offline tests for the DATABASE_URL normalizer.

Railway's Postgres plugin occasionally hands out a URL starting with `postgres://`,
which SQLAlchemy 2.0 refuses. The normalizer should rewrite it to `postgresql://`
once, while leaving already-correct URLs alone.
"""

import pytest
from app.config import _normalize_database_url, Settings


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("postgres://u:p@h:5432/db", "postgresql://u:p@h:5432/db"),
        ("postgres://u:p@h/db", "postgresql://u:p@h/db"),
        ("postgresql://u:p@h/db", "postgresql://u:p@h/db"),
        ("sqlite:///./chessania.sqlite3", "sqlite:///./chessania.sqlite3"),
    ],
)
def test_normalize_database_url(raw: str, expected: str) -> None:
    assert _normalize_database_url(raw) == expected


def test_settings_normalizes_postgres_url(monkeypatch) -> None:
    """The Settings class applies the normalizer on load."""
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h/db")
    s = Settings()
    assert s.DATABASE_URL == "postgresql://u:p@h/db"

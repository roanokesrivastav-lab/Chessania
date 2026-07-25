"""The database engine and session factory.

Why this file is so short: SQLAlchemy is the layer that makes local SQLite
and production Postgres look identical to the rest of the app. Everywhere
else in the codebase just asks this module for a session and never knows
or cares which database is actually underneath — same models.py, same
queries, same code, whether DATABASE_URL points at a .sqlite3 file on your
laptop or a Postgres instance on Railway.

SQLite needs one extra flag (`check_same_thread=False`) because FastAPI can
hand a request to a different thread than the one that opened the
connection; Postgres has no such restriction.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Session:
    """Yield-style dependency for FastAPI routes (wired up once routes exist)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

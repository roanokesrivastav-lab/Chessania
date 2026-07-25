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

SQLite also has a second, easy-to-miss quirk: it ignores `ON DELETE CASCADE`
(the behavior Appendix 1 specifies for every foreign key in this schema)
unless each connection explicitly turns foreign-key enforcement on. Without
the `PRAGMA foreign_keys=ON` below, deleting a Player in local dev would
silently leave that player's Games/MoveEvals/Reports behind as orphans —
while the exact same code against Postgres in prod would correctly cascade.
That's precisely the kind of dev/prod divergence this file exists to
prevent, so it's wired here rather than left as a surprise for later.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")


def enable_sqlite_foreign_keys(target_engine: Engine) -> None:
    """Turn on FK enforcement for every connection this engine opens.

    Exported so tests can apply the same fix to their own throwaway SQLite
    engines (see tests/test_api.py) — the singleton `engine` below is bound
    to the dev database file, not something a test should import and share.
    """

    @event.listens_for(target_engine, "connect")
    def _on_connect(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:
    enable_sqlite_foreign_keys(engine)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Session:
    """Yield-style dependency for FastAPI routes (wired up once routes exist)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""Every tunable the backend uses, in one place.

Session 3 rule (CLAUDE.md #3 / roadmap A2 Rule 1): no tunable number is ever
hardcoded at a call site. If code needs a number or a path, it imports
`settings` from here — never a bare literal. That's what lets Session 24
(deploy) swap SQLite for Postgres, or a future tuning pass move SF_DEPTH,
without hunting through the codebase.

Read once at import time from environment variables / a `.env` file, with
defaults sane enough to run entirely locally with zero configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database — SQLite locally, Postgres in prod (see app/db.py).
    DATABASE_URL: str = "sqlite:///./chessania.sqlite3"

    # Stockfish (wired up starting Session 4).
    SF_PATH: str = "stockfish"
    SF_DEPTH: int = 12  # ceiling 14 — see roadmap Locked Decisions

    # Ingestion (Session 5+).
    MAX_GAMES: int = 20
    CONTACT_EMAIL: str = "contact@example.com"  # goes in the Chess.com User-Agent

    # Jobs (Session 10+). In-memory registry, no external queue (Locked 9).
    MAX_CONCURRENT_JOBS: int = 2

    # CORS (wired into main.py once routes exist). Comma-separated origins.
    CORS_ORIGINS: str = "http://localhost:3000"

    # dev | prod — gates things like debug endpoints (Session 12+).
    ENV: str = "dev"


settings = Settings()

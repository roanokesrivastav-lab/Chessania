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

    # Features (Session 12+).
    FEATURE_OPENING_LEAK_CP: int = 150
    FEATURE_ENDGAME_AHEAD_CP: int = 200
    FEATURE_TREND_MIN_GAMES: int = 8
    FEATURE_TREND_BAND: float = 0.10  # relative first-half vs second-half band
    FEATURE_COLOR_MIN_GAMES: int = 4  # below this, per-color numbers are low-signal

    # Detectors (Session 13). Six precision-first pattern detectors over
    # already-stored move_evals — see app/detectors.py's module docstring for
    # why "precision-first" matters (a wrongly-firing detector reads as a
    # horoscope, not a coach).
    DET_HUNG_MIN_SHARE: float = 0.30  # hung_pieces: share of blunders that hang material
    DET_SEE_MINOR_CP: int = 300  # hung_pieces: min SEE value to count as "hung"
    DET_LATE_PLY: int = 30  # late_collapse: early/late boundary
    DET_LATE_RATIO: float = 2.0  # late_collapse: late rate must be >= this x early rate
    DET_LATE_MIN_BLUNDERS: int = 4  # late_collapse: min late player-blunder count to fire
    DET_OPENING_FAMILY_MIN_GAMES: int = 5  # opening_leak: min games in an ECO family
    DET_OPENING_LEAK_CP: int = 40  # opening_leak: avg ply-15 player-POV eval threshold
    DET_OVEREXT_DROP_CP: int = 150  # overextension: eval drop within the window
    DET_OVEREXT_WINDOW: int = 6  # overextension: plies after the pawn push to check
    DET_OVEREXT_MIN: int = 3  # overextension: min occurrences across games to fire
    DET_BLITZ_RATIO: float = 1.8  # time_class_split: blitz rate must be >= this x rapid rate
    DET_TIMECLASS_MIN_GAMES: int = 5  # time_class_split: min games of EACH time class
    DET_PLAYABLE_CP: int = 150  # turning_point: "still playable" player-POV eval floor

    # Time-coaching detectors (Session 13+ extension). All thresholds are
    # read from stored PGN clock stamps and seconds_spent — no engine/network.
    DET_TIME_RUSH_SECONDS: int = 15  # rushed_blunders: "low remaining clock" threshold (s)
    DET_TIME_RUSH_MIN_SHARE: float = 0.40  # rushed_blunders: share of blunders at low clock to fire
    DET_TIME_RUSH_MIN_BLUNDERS: int = 4  # rushed_blunders: min clocked player blunders to judge
    DET_TIME_TROUBLE_CLOCK: int = 30  # time_trouble_collapse: "in time trouble" clock (s)
    DET_TIME_TROUBLE_RATIO: float = 2.0  # time_trouble_collapse: low-clock error rate >= this x normal
    DET_TIME_TROUBLE_MIN_GAMES: int = 5  # time_trouble_collapse: min games that reached time trouble
    DET_TIME_DAWDLE_SECONDS: int = 20  # dawdling: seconds_spent on an ok move to count as dawdling
    DET_TIME_DAWDLE_MIN_GAMES: int = 5  # dawdling: min games to fire
    DET_TIME_DAWDLE_MAX_LEGAL: int = 8  # dawdling complexity gate: only ok-moves in positions with <= this many legal moves count (honors the LOCKED RULE)

    # Coaching / rule engine (Session 15). All coach thresholds live here so
    # the rule table in app/coach.py has no bare numbers.
    COACH_BLUNDER_RATE: float = 1.5  # blunder_rate rule fires when meaningful blunders/game exceeds this
    COACH_OPENING_GENERAL: float = 0.35  # opening_general rule fires when opening leak rate is at least this
    COACH_ENDGAME_CONVERSION: float = 0.60  # endgame_conversion rule fires when conversion is below this


settings = Settings()

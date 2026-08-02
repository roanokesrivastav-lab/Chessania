"""SQLAlchemy ORM models — mirrors roadmap Appendix 1 exactly.

Appendix 1 is written as Postgres DDL and is the schema's law (CLAUDE.md #3):
nothing here may invent, rename, or drop a field. Two spots need a portable
substitute for a Postgres-only server default so the *same* code creates the
*same* shape on SQLite (dev) and Postgres (prod) — noted inline where they
occur; the column types, constraints, and indexes are otherwise identical
to the appendix.

Five tables, five reasons they exist:

- players     Identity is the pair (platform, username) — there is no login
              anywhere in this product (Locked Decision 2). One row per
              player we've ever looked up.
- games       One row per fetched game, PGN kept verbatim so nothing is ever
              re-fetched from Chess.com/Lichess to re-derive a fact.
- move_evals  The pipeline's ground truth: one row per half-move (ply) of
              every analyzed game, in White's point of view (converted to
              the mover's perspective only by the cp_loss() helper in S9).
              `classification` includes 'skipped' because a move played in
              an already-decided position (crushing/lost) isn't a
              meaningful data point — counting it would poison every rate
              computed downstream.
- eval_cache  Stockfish is slow; many players share the same opening
              position. This table means we never pay the engine twice for
              an identical (fen, depth) — a huge speed win across users.
- reports     The product's actual output, stored whole as JSON so it can
              be re-served instantly and compared against future reports
              for the same player (progress tracking, S22).

What's deliberately absent, so nobody "helpfully" adds it later: no
users/auth tables (Locked 2), no jobs table (the job registry is in-memory
only, Locked 9 — Part G #9 holds the seat for a durable queue), no
puzzles/chat/social tables (Part G), no per-rule config table (the rule
engine is code + Appendix 3, and that's correct at this scale).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator):
    """A UUID column that works on both Postgres and SQLite.

    Appendix 1 specifies `uuid primary key default gen_random_uuid()` —
    a Postgres-only function. SQLite has no UUID type or equivalent
    function at all. This type stores a real UUID either way: Postgres's
    native UUID column in prod, a 36-character string in SQLite for dev.
    The default is generated in Python (`uuid.uuid4()`, below) instead of
    on the server, which is what makes one line of model code create an
    equivalent column on either database.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(value)


class Base(DeclarativeBase):
    pass


class Player(Base):
    """Identity = (platform, username). No password column exists or ever will."""

    __tablename__ = "players"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)  # stored lowercased, always
    rating_snapshot: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("platform in ('chesscom','lichess')", name="players_platform_check"),
        UniqueConstraint("platform", "username", name="players_platform_username_key"),
    )


class Game(Base):
    """One row per fetched game. The PGN is retained verbatim."""

    __tablename__ = "games"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    platform_game_id: Mapped[str] = mapped_column(Text, nullable=False)  # chess.com game URL / lichess game id
    game_url: Mapped[str] = mapped_column(Text, nullable=False)  # deep link used in report evidence
    pgn: Mapped[str] = mapped_column(Text, nullable=False)
    time_class: Mapped[str] = mapped_column(Text, nullable=False)
    player_color: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    player_rating: Mapped[int | None] = mapped_column(Integer)
    opponent_rating: Mapped[int | None] = mapped_column(Integer)
    played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opening_eco: Mapped[str | None] = mapped_column(Text)  # e.g. 'B12'
    opening_name: Mapped[str | None] = mapped_column(Text)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # null = not yet analyzed (job skip-key)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("time_class in ('rapid','blitz')", name="games_time_class_check"),
        CheckConstraint("player_color in ('white','black')", name="games_player_color_check"),
        CheckConstraint("result in ('win','loss','draw')", name="games_result_check"),
        UniqueConstraint("player_id", "platform_game_id", name="games_player_id_platform_game_id_key"),  # the dedupe law (S6)
        Index("games_player_idx", "player_id"),
        Index("games_analyzed_idx", "player_id", "analyzed_at"),
    )


class MoveEval(Base):
    """One row per half-move (ply) of an analyzed game. ALL evals White-POV (S8 law)."""

    __tablename__ = "move_evals"

    # Postgres: an auto-incrementing bigint identity column. SQLite: an
    # ordinary INTEGER PRIMARY KEY (SQLite's own rowid-backed autoincrement) —
    # `with_variant` picks the right one per dialect from one declaration.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    ply: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based half-move number
    move_san: Mapped[str] = mapped_column(Text, nullable=False)
    fen_before: Mapped[str] = mapped_column(Text, nullable=False)
    eval_cp_before: Mapped[int] = mapped_column(Integer, nullable=False)  # White POV, clamped ±1000, mate=±1000
    eval_cp_after: Mapped[int] = mapped_column(Integer, nullable=False)
    cp_loss: Mapped[int] = mapped_column(Integer, nullable=False)  # mover's POV, floored at 0 (S9 helper)
    best_move_san: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    # Player's clock time spent on this move, in seconds. Nullable: null when the
    # PGN carries no clock data. Populated in Session 9 from the PGN's [%clk]
    # comments; CAPTURED for future v2 time-management coaching (roadmap Part G #11),
    # NOT read by any v1 feature, detector, or rule. Added by the 2026-07-25 amendment.
    seconds_spent: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        CheckConstraint(
            "classification in ('ok','inaccuracy','mistake','blunder','skipped')",
            name="move_evals_classification_check",
        ),
        CheckConstraint(
            "phase in ('opening','middlegame','endgame')", name="move_evals_phase_check"
        ),
        UniqueConstraint("game_id", "ply", name="move_evals_game_id_ply_key"),
        Index("move_evals_game_idx", "game_id"),
        Index("move_evals_class_idx", "game_id", "classification"),
    )


class EvalCache(Base):
    """Never pay Stockfish twice for the same (fen, depth) (S8)."""

    __tablename__ = "eval_cache"

    fen: Mapped[str] = mapped_column(Text, primary_key=True)
    depth: Mapped[int] = mapped_column(Integer, primary_key=True)
    eval_cp: Mapped[int] = mapped_column(Integer, nullable=False)  # White POV, clamped
    best_move_uci: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Report(Base):
    """The product's output, whole, as JSON conforming to Appendix 2."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    games_analyzed: Mapped[int] = mapped_column(Integer, nullable=False)
    first_game_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # date range shown in the header
    last_game_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("reports_player_idx", "player_id", desc("created_at")),)


# ── V2-S2: Auth ───────────────────────────────────────────────────────
# These two tables are separate from the v1 Player/Game/MoveEval pipeline
# (Locked 5: v1 routes never require auth). Users are v2-only.


class User(Base):
    """A v2 account — one of email (magic-link verified) or lichess_id
    (OAuthed) must be set; both can be set when linking accounts."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    lichess_id: Mapped[str | None] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_anon_id: Mapped[str | None] = mapped_column(Text)  # last guest id — lets a sign-in adopt progress
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "email IS NOT NULL OR lichess_id IS NOT NULL",
            name="users_at_least_one_identity",
        ),
    )


class MagicLinkToken(Base):
    """Single-use, short-TTL magic-link token. The raw token is NEVER stored —
    only its SHA-256 hash (token_hash) is persisted, so a DB leak reveals
    nothing usable. `used_at` is NULL until the token is consumed; a non-NULL
    `used_at` + the 15-minute TTL on `expires_at` together enforce single-use."""

    __tablename__ = "magic_link_tokens"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ── V2-S3: Position mining ────────────────────────────────────────────


class TrainingPosition(Base):
    """A position mined from the player's own analyzed games, accumulating
    across every analysis. The bank belongs to the analyzed PLAYER identity
    (not a v2 User) — it exists independent of accounts/sign-in.

    Dedupe key: (player_id, source_game_id, ply, category). Running mining
    twice adds zero duplicates — idempotent by design (M2).

    eval_before_cp is stored WHITE-POV, exactly copied from MoveEval —
    never store a player-POV-converted number (CLAUDE.md rule 7).
    best_line_uci is the engine's best move in UCI notation, converted from
    MoveEval.best_move_san at mine time."""

    __tablename__ = "training_positions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("players.id", ondelete="CASCADE"), nullable=False
    )
    source_game_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    fen: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    best_line_uci: Mapped[str] = mapped_column(Text, nullable=False)
    eval_before_cp: Mapped[int] = mapped_column(Integer, nullable=False)  # White POV
    mined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "category in ('blunder','unconverted','danger')",
            name="training_positions_category_check",
        ),
        UniqueConstraint(
            "player_id",
            "source_game_id",
            "ply",
            "category",
            name="training_positions_dedupe_key",
        ),
        Index("training_positions_player_idx", "player_id"),
    )

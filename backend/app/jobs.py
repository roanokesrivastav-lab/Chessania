"""The in-memory job registry (Locked Decision 9): no external queue, no
jobs table in the database (see app/models.py's module docstring). A single
process-local dict tracks every analysis job's progress so the frontend can
poll `GET /api/jobs/{job_id}` while `POST /api/analyze` returns instantly.

Accepted v1 tradeoff: the registry lives only in this process's memory, so
a server restart forgets every in-flight and completed job. Roadmap Part G
#9 holds the seat for a durable queue (Redis/Postgres-backed) if that ever
becomes a real problem; until then this is simpler and it's enough.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass

from sqlalchemy import select

from app.analysis import analyze_game
from app.config import settings
from app.coach import build_report
from app.db import SessionLocal
from app.engine_eval import StockfishEvaluator
from app.features import load_features
from app.ingest import (
    NoEligibleGames,
    PlayerNotFound,
    UpstreamError,
    UpstreamRateLimited,
    fetch_games,
    persist_games,
    upsert_player,
)
from app.models import Game, Report as ReportModel


@dataclass
class JobStatus:
    job_id: str
    platform: str
    username: str
    state: str  # queued | running | done | error
    stage: str  # fetching | analyzing | coaching
    mode: str = "standard"  # standard (fast 20-game default) | deep (opt-in ~100, S33)
    current_game: int = 0
    total_games: int = 0
    error_message: str | None = None
    report_ready: bool = False

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "platform": self.platform,
            "username": self.username,
            "state": self.state,
            "stage": self.stage,
            "mode": self.mode,
            "current_game": self.current_game,
            "total_games": self.total_games,
            "error_message": self.error_message,
            "report_ready": self.report_ready,
        }


# Module-global registry — see the module docstring for why this dies on
# restart and why that's an accepted tradeoff for v1.
_registry: dict[str, JobStatus] = {}
_lock = threading.Lock()
_semaphore = threading.Semaphore(settings.MAX_CONCURRENT_JOBS)
# S33: deep runs are long and Stockfish-heavy — only one runs at a time,
# on top of (not instead of) the main concurrency semaphore.
_deep_semaphore = threading.Semaphore(settings.MAX_CONCURRENT_DEEP_JOBS)

_LIVE_STATES = ("queued", "running")


def _platform_label(platform: str) -> str:
    return "Chess.com" if platform == "chesscom" else "Lichess"


def get_or_create_job(
    platform: str, username: str, mode: str = "standard"
) -> tuple[JobStatus, bool]:
    """Return (job, deduped). If a live (queued/running) job already exists
    for this (platform, username, mode) triple, return it with deduped=True
    instead of starting a second one — two browser tabs hitting analyze for
    the same account should share one job, not race two.

    Mode is part of the dedup match (S33): a deep request must NOT join a
    live standard job — it's a different (much longer) analysis."""
    with _lock:
        for job in _registry.values():
            if (
                job.platform == platform
                and job.username.lower() == username.lower()
                and job.mode == mode
                and job.state in _LIVE_STATES
            ):
                return job, True

        job = JobStatus(
            job_id=str(uuid.uuid4()),
            platform=platform,
            username=username,
            state="queued",
            stage="fetching",
            mode=mode,
        )
        _registry[job.job_id] = job
        return job, False


def get_job(job_id: str) -> JobStatus | None:
    return _registry.get(job_id)


def run_job(job_id: str) -> None:
    """The background job body. Runs synchronously in FastAPI's threadpool
    (BackgroundTasks), one call per job. Acquires the concurrency semaphore
    FIRST so that jobs beyond MAX_CONCURRENT_JOBS sit blocked here — still
    reporting state="queued" to anyone polling — rather than all running at
    once and hammering Stockfish/the upstream APIs simultaneously.

    S33: a "deep" job also acquires the deep semaphore (one deep run at a
    time) and fetches up to MAX_GAMES_DEEP games instead of MAX_GAMES."""
    job = get_job(job_id)
    if job is None:
        return

    _semaphore.acquire()
    deep = job.mode == "deep"
    if deep:
        _deep_semaphore.acquire()
    # session/evaluator are created INSIDE the try so that a failure to open
    # the engine (bad SF_PATH) or the DB is caught like any other error and
    # lands the job in state="error" — never leaving it stuck "running" with a
    # leaked engine process. Both are guarded in the finally (may still be None).
    session = None
    evaluator = None
    try:
        job.state = "running"
        session = SessionLocal()
        evaluator = StockfishEvaluator(cache_session=session)

        job.stage = "fetching"
        max_games = settings.MAX_GAMES_DEEP if deep else settings.MAX_GAMES
        games = fetch_games(job.platform, job.username, max_games=max_games)
        player = upsert_player(
            session,
            job.platform,
            job.username,
            games[0].player_rating if games else None,
        )
        persist_games(session, player, games)

        unanalyzed = session.scalars(
            select(Game).where(Game.player_id == player.id, Game.analyzed_at.is_(None))
        ).all()

        job.stage = "analyzing"
        job.total_games = len(unanalyzed)
        for i, game in enumerate(unanalyzed, start=1):
            analyze_game(game, evaluator, session)
            job.current_game = i

        job.stage = "coaching"
        features = load_features(session, job.platform, job.username)
        if features is not None:
            report = build_report(features, session, player, mode=job.mode)
            # Persist the report so /api/reports can serve it instantly.
            games = list(
                session.scalars(
                    select(Game).where(Game.player_id == player.id, Game.analyzed_at.is_not(None))
                ).all()
            )
            first_game_at = min((g.played_at for g in games if g.played_at is not None), default=None)
            last_game_at = max((g.played_at for g in games if g.played_at is not None), default=None)
            session.add(
                ReportModel(
                    player_id=player.id,
                    games_analyzed=len(games),
                    first_game_at=first_game_at,
                    last_game_at=last_game_at,
                    report_json=report.model_dump(mode="json"),
                )
            )
            session.commit()
            job.report_ready = True

        job.state = "done"
    except PlayerNotFound:
        job.state = "error"
        job.error_message = (
            f"We couldn't find that username on {_platform_label(job.platform)} "
            "— check the spelling?"
        )
    except NoEligibleGames:
        job.state = "error"
        job.error_message = "No recent rapid or blitz games found for that account."
    except UpstreamRateLimited:
        job.state = "error"
        job.error_message = (
            f"{_platform_label(job.platform)} is busy right now — try again in a minute."
        )
    except UpstreamError:
        job.state = "error"
        job.error_message = (
            f"Something went wrong reaching {_platform_label(job.platform)} — "
            "try again shortly."
        )
    except Exception:
        job.state = "error"
        job.error_message = "Analysis hit an unexpected error — please try again."
    finally:
        if evaluator is not None:
            evaluator.close()
        if session is not None:
            session.close()
        _semaphore.release()
        if deep:
            _deep_semaphore.release()

"""The in-memory job registry and its two HTTP routes, fully offline.

No real network call and no real Stockfish process ever run here: the
endpoint tests monkeypatch app.jobs.run_job to a no-op so the
BackgroundTask FastAPI schedules never actually fetches or analyzes
anything (Rule 5: the suite is offline and deterministic).
"""

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import jobs, main
from app.db import enable_sqlite_foreign_keys
from app.engine_eval import EvalResult
from app.main import app
from app.models import Base, Game, MoveEval, Player
from tests.conftest import load_json_fixture

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_registry():
    """The registry is module-global — clear it before and after every test
    so state never leaks between tests (jobs.py's own docstring warns this
    dies on restart; leaking across tests would be the same bug in miniature)."""
    jobs._registry.clear()
    yield
    jobs._registry.clear()


# ---------------------------------------------------------------------------
# Registry unit tests
# ---------------------------------------------------------------------------


def test_get_or_create_job_creates_a_queued_job():
    job, deduped = jobs.get_or_create_job("chesscom", "alice")
    assert deduped is False
    assert job.job_id
    assert job.state == "queued"
    assert job.stage == "fetching"
    assert jobs.get_job(job.job_id) is job


def test_second_call_for_same_live_job_is_deduped():
    job1, deduped1 = jobs.get_or_create_job("chesscom", "alice")
    assert deduped1 is False

    job2, deduped2 = jobs.get_or_create_job("chesscom", "Alice")  # case-insensitive
    assert deduped2 is True
    assert job2.job_id == job1.job_id

    # Once the job is no longer live, a fresh request starts a new job.
    job1.state = "done"
    job3, deduped3 = jobs.get_or_create_job("chesscom", "alice")
    assert deduped3 is False
    assert job3.job_id != job1.job_id


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


def test_analyze_rejects_invalid_username(monkeypatch):
    monkeypatch.setattr(main, "run_job", lambda job_id: None)
    resp = client.post("/api/analyze", json={"platform": "chesscom", "username": "x"})
    assert resp.status_code == 400


def test_analyze_returns_job_id_for_valid_username(monkeypatch):
    monkeypatch.setattr(main, "run_job", lambda job_id: None)
    resp = client.post("/api/analyze", json={"platform": "chesscom", "username": "validuser"})
    assert resp.status_code == 200
    assert "job_id" in resp.json()


def test_job_status_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(main, "run_job", lambda job_id: None)
    resp = client.post("/api/analyze", json={"platform": "lichess", "username": "someone"})
    job_id = resp.json()["job_id"]

    status_resp = client.get(f"/api/jobs/{job_id}")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert "state" in body
    assert "stage" in body
    assert "current_game" in body
    assert "total_games" in body


def test_job_status_404_for_unknown_id():
    resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# run_job — the full job body, end to end, still fully offline (S13)
#
# The tests above monkeypatch run_job to a no-op so they never touch the job
# BODY itself, only the routes around it. These exercise run_job for real:
# respx mocks the outgoing Chess.com fetch (reusing test_ingest.py's
# recorded fixtures — no real network), and StubEvaluator stands in for
# StockfishEvaluator (no real engine process) so the whole fetch -> persist
# -> analyze -> state-transition pipeline runs and is asserted end to end.
# ---------------------------------------------------------------------------


class StubEvaluator:
    """No-engine drop-in for StockfishEvaluator. Resolves every position to
    a flat eval_cp=0 with 'best move' = that position's own first legal move
    — an arbitrary but always-valid choice; analyze_game only needs SOME
    best_move_uci to record, never a real evaluation, for a job-completion
    test like this. Same (cache_session=...) constructor shape as the real
    evaluators so app/jobs.py's `StockfishEvaluator(cache_session=session)`
    call site works unmodified."""

    def __init__(self, cache_session=None):
        self.cache_session = cache_session

    def evaluate(self, board):
        first_legal = next(iter(board.legal_moves))
        return EvalResult(eval_cp=0, best_move_uci=first_legal.uci())

    def close(self):
        pass


def _test_session_factory():
    """A fresh in-memory SQLite engine + sessionmaker, tables created from
    the models' metadata — the same shape as app.db.SessionLocal, but
    pointed at a throwaway test database instead of the real dev one.
    StaticPool (one shared connection) rather than SQLite's default
    per-thread pool: nothing here strictly needs cross-thread access since
    run_job is called directly (not via BackgroundTasks' worker thread), but
    it costs nothing and matches the same safe pattern test_debug_endpoint.py
    needs for the real threaded case."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_foreign_keys(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@respx.mock
def test_run_job_drives_to_done_with_offline_fetch_and_evaluator(monkeypatch):
    """Full run_job integration: fetch (respx-mocked, real recorded fixture
    content), persist, analyze (StubEvaluator, no engine), and the state
    transition to 'done' — all in one call, all offline."""
    test_session_local = _test_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", test_session_local)
    monkeypatch.setattr(jobs, "StockfishEvaluator", StubEvaluator)

    archives = load_json_fixture("api", "chesscom_archives.json")
    month = load_json_fixture("api", "chesscom_month.json")
    respx.get("https://api.chess.com/pub/player/fixture_user/games/archives").mock(
        return_value=httpx.Response(200, json=archives)
    )
    respx.get("https://api.chess.com/pub/player/fixture_user/games/2026/06").mock(
        return_value=httpx.Response(200, json=month)
    )

    job, _deduped = jobs.get_or_create_job("chesscom", "fixture_user")
    jobs.run_job(job.job_id)

    assert job.state == "done"
    assert job.error_message is None

    with test_session_local() as session:
        player = (
            session.query(Player)
            .filter_by(platform="chesscom", username="fixture_user")
            .one()
        )
        games = session.query(Game).filter_by(player_id=player.id).all()
        # Matches test_ingest.py's happy-path fixture: 3 eligible games
        # (bullet and chess960 excluded).
        assert len(games) == 3
        assert all(g.analyzed_at is not None for g in games)
        assert session.query(MoveEval).count() > 0


@respx.mock
def test_run_job_ends_in_error_with_friendly_message_on_404(monkeypatch):
    """A 404 from Chess.com (unknown username) must land the job in
    state='error' with the friendly "couldn't find that username" copy —
    never an unhandled exception or a raw traceback."""
    test_session_local = _test_session_factory()
    monkeypatch.setattr(jobs, "SessionLocal", test_session_local)
    monkeypatch.setattr(jobs, "StockfishEvaluator", StubEvaluator)

    respx.get("https://api.chess.com/pub/player/ghostplayer/games/archives").mock(
        return_value=httpx.Response(404)
    )

    job, _deduped = jobs.get_or_create_job("chesscom", "ghostplayer")
    jobs.run_job(job.job_id)

    assert job.state == "error"
    assert "couldn't find that username" in job.error_message
